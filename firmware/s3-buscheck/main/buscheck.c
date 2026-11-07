#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "cJSON.h"
#include "esp_bt.h"
#include "esp_bt_main.h"
#include "esp_bt_device.h"
#include "esp_event.h"
#include "esp_gap_ble_api.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "payload.h"

#define DONE BIT0
#define INIT_DONE BIT1
#define CONTROL_TIMEOUT_MS 700
static const char *TAG = "Buscheck";
static portMUX_TYPE state_lock = portMUX_INITIALIZER_UNLOCKED;
static SemaphoreHandle_t control_lock;
static EventGroupHandle_t events;
static struct {
    bool ready, running, pending;
    uint32_t sent; // controller-confirmed starts, not an on-air packet count
    char error[128];
} state;
static esp_bt_status_t init_status;

static void error_set(const char *where, int code)
{
    portENTER_CRITICAL(&state_lock);
    snprintf(state.error, sizeof(state.error), "%s (%d)", where, code);
    portEXIT_CRITICAL(&state_lock);
    ESP_LOGE(TAG, "%s (%d)", where, code);
}

static bool check(esp_err_t err, const char *where)
{
    if (err == ESP_OK) return true;
    error_set(where, err);
    return false;
}

static void status_json(char *out, size_t size)
{
    bool running;
    uint32_t sent;
    char error[sizeof(state.error)];
    portENTER_CRITICAL(&state_lock);
    running = state.running;
    sent = state.sent;
    memcpy(error, state.error, sizeof(error));
    portEXIT_CRITICAL(&state_lock);
    // cjson escapes errors before http and serial json
    cJSON *json = cJSON_CreateObject();
    if (json && cJSON_AddBoolToObject(json, "running", running) &&
        cJSON_AddNumberToObject(json, "sent", sent) &&
        cJSON_AddStringToObject(json, "error", error) &&
        cJSON_PrintPreallocated(json, out, size, false)) {
        cJSON_Delete(json);
        return;
    }
    cJSON_Delete(json);
    snprintf(out, size, "{\"running\":%s,\"sent\":%" PRIu32
             ",\"error\":\"Status allocation failed\"}", running ? "true" : "false", sent);
}

static void gap_callback(esp_gap_ble_cb_event_t event, esp_ble_gap_cb_param_t *p)
{
    if (event == ESP_GAP_BLE_EXT_ADV_SET_PARAMS_COMPLETE_EVT ||
        event == ESP_GAP_BLE_EXT_ADV_DATA_SET_COMPLETE_EVT) {
        init_status = event == ESP_GAP_BLE_EXT_ADV_SET_PARAMS_COMPLETE_EVT ?
                      p->ext_adv_set_params.status : p->ext_adv_data_set.status;
        if (init_status != ESP_BT_STATUS_SUCCESS) error_set("Advertising setup failed", init_status);
        xEventGroupSetBits(events, INIT_DONE);
    } else if (event == ESP_GAP_BLE_EXT_ADV_START_COMPLETE_EVT ||
               event == ESP_GAP_BLE_EXT_ADV_STOP_COMPLETE_EVT) {
        bool start = event == ESP_GAP_BLE_EXT_ADV_START_COMPLETE_EVT;
        esp_bt_status_t status = start ? p->ext_adv_start.status : p->ext_adv_stop.status;
        portENTER_CRITICAL(&state_lock);
        if (status == ESP_BT_STATUS_SUCCESS) {
            state.running = start;
            if (start) state.sent++;
            state.error[0] = '\0';
        }
        portEXIT_CRITICAL(&state_lock);
        if (status != ESP_BT_STATUS_SUCCESS) error_set(start ? "Start failed" : "Stop failed", status);
        // publish completion before a new command; a late callback could wake the next one
        xEventGroupSetBits(events, DONE);
        portENTER_CRITICAL(&state_lock);
        state.pending = false;
        portEXIT_CRITICAL(&state_lock);
    } else if (event == ESP_GAP_BLE_ADV_TERMINATED_EVT) {
        portENTER_CRITICAL(&state_lock);
        state.running = false;
        portEXIT_CRITICAL(&state_lock);
        error_set("Advertising ended unexpectedly", p->adv_terminate.status);
    }
}

// never report running from a queued request; a late callback resolves a timeout
static bool control(bool start)
{
    if (xSemaphoreTake(control_lock, pdMS_TO_TICKS(50)) != pdTRUE) {
        error_set("Control busy", ESP_ERR_TIMEOUT);
        return false;
    }
    portENTER_CRITICAL(&state_lock);
    bool ready = state.ready, pending = state.pending, running = state.running;
    portEXIT_CRITICAL(&state_lock);
    bool ok = false;
    if (!ready || pending) {
        error_set(pending ? "Please wait for the current change" : "Bluetooth not ready", ESP_ERR_INVALID_STATE);
        goto end;
    }
    if (running == start) { ok = true; goto end; }
    xEventGroupClearBits(events, DONE);
    portENTER_CRITICAL(&state_lock);
    state.pending = true;
    portEXIT_CRITICAL(&state_lock);
    const esp_ble_gap_ext_adv_t adv = {.instance = 0, .duration = 0, .max_events = 0};
    const uint8_t instance = 0;
    esp_err_t err = start ? esp_ble_gap_ext_adv_start(1, &adv) : esp_ble_gap_ext_adv_stop(1, &instance);
    if (err != ESP_OK) {
        portENTER_CRITICAL(&state_lock);
        state.pending = false;
        portEXIT_CRITICAL(&state_lock);
        error_set(start ? "Start request failed" : "Stop request failed", err);
    } else if (!(xEventGroupWaitBits(events, DONE, pdTRUE, pdTRUE,
                                   pdMS_TO_TICKS(CONTROL_TIMEOUT_MS)) & DONE)) {
        error_set("Controller response timed out", ESP_ERR_TIMEOUT);
    } else {
        portENTER_CRITICAL(&state_lock);
        ok = state.running == start && state.error[0] == '\0';
        portEXIT_CRITICAL(&state_lock);
    }
end:
    xSemaphoreGive(control_lock);
    return ok;
}

static bool setup_wait(esp_err_t err)
{
    if (!check(err, "Advertising setup request failed")) return false;
    if (!(xEventGroupWaitBits(events, INIT_DONE, pdTRUE, pdTRUE, pdMS_TO_TICKS(2000)) & INIT_DONE)) {
        error_set("Advertising setup timed out", ESP_ERR_TIMEOUT);
        return false;
    }
    return init_status == ESP_BT_STATUS_SUCCESS;
}

static void bluetooth_init(void)
{
    esp_bt_controller_config_t config = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    if (!check(esp_bt_controller_init(&config), "Controller init failed") ||
        !check(esp_bt_controller_enable(ESP_BT_MODE_BLE), "Controller enable failed") ||
        !check(esp_bluedroid_init(), "Bluetooth init failed") ||
        !check(esp_bluedroid_enable(), "Bluetooth enable failed") ||
        !check(esp_ble_gap_register_callback(gap_callback), "Callback setup failed")) return;
    const esp_ble_gap_ext_adv_params_t params = {
        .type = ESP_BLE_GAP_SET_EXT_ADV_PROP_NONCONN_NONSCANNABLE_UNDIRECTED,
        .interval_min = 160, .interval_max = 160, // 100 ms plus controller delay
        .channel_map = ADV_CHNL_ALL,
        .own_addr_type = BLE_ADDR_TYPE_PUBLIC,
        .filter_policy = ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY,
        .primary_phy = ESP_BLE_GAP_PHY_1M,
        .secondary_phy = ESP_BLE_GAP_PHY_1M,
        .tx_power = EXT_ADV_TX_PWR_NO_PREFERENCE,
        .sid = 0,
    };
    if (!setup_wait(esp_ble_gap_ext_adv_set_params(0, &params)) ||
        !setup_wait(esp_ble_gap_config_ext_adv_data_raw(0, sizeof(buscheck_payload), buscheck_payload))) return;
    const uint8_t *address = esp_bt_dev_get_address();
    ESP_LOGI(TAG, "BLE %02x:%02x:%02x:%02x:%02x:%02x payload=%u bytes; stopped until Start",
             address[0], address[1], address[2], address[3], address[4], address[5], (unsigned)sizeof(buscheck_payload));
    portENTER_CRITICAL(&state_lock);
    state.ready = true;
    portEXIT_CRITICAL(&state_lock);
}

static void shutdown_stop(void)
{
    // stop and wait before a software reset; a power cycle resets the controller
    portENTER_CRITICAL(&state_lock);
    bool ready = state.ready;
    portEXIT_CRITICAL(&state_lock);
    if (ready) control(false);
}

extern const unsigned char page_start[] asm("_binary_index_html_start");
extern const unsigned char page_end[] asm("_binary_index_html_end");

static esp_err_t page_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html; charset=utf-8");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    return httpd_resp_send(req, (const char *)page_start, page_end - page_start - 1);
}

static esp_err_t api_handler(httpd_req_t *req)
{
    bool ok = true;
    if (req->user_ctx) ok = control(strcmp(req->user_ctx, "start") == 0);
    char json[512];
    status_json(json, sizeof(json));
    if (!ok) httpd_resp_set_status(req, "503 Service Unavailable");
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    ESP_LOGI(TAG, "%s %s", req->uri, json);
    return httpd_resp_sendstr(req, json);
}

static bool ap_init(void)
{
    if (!check(esp_netif_init(), "Network init failed") ||
        !check(esp_event_loop_create_default(), "Event loop failed")) return false;
    esp_netif_t *ap = esp_netif_create_default_wifi_ap();
    if (!ap) { error_set("AP interface failed", ESP_ERR_NO_MEM); return false; }
    // the default ap interface runs dhcp at 192.168.4.1/24
    wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
    wifi_config_t wifi = {.ap = {
        .ssid = "janosch", .ssid_len = 7, .password = "Jan0sch?!",
        .channel = 1, .max_connection = 4, .authmode = WIFI_AUTH_WPA2_PSK,
    }};
    if (!check(esp_wifi_init(&config), "Wi-Fi init failed") ||
        !check(esp_wifi_set_storage(WIFI_STORAGE_RAM), "Wi-Fi storage failed") ||
        !check(esp_wifi_set_mode(WIFI_MODE_AP), "AP mode failed") ||
        !check(esp_wifi_set_config(WIFI_IF_AP, &wifi), "AP config failed") ||
        !check(esp_wifi_start(), "AP start failed")) return false;
    ESP_LOGI(TAG, "Wi-Fi janosch; http://192.168.4.1/ (no internet needed)");
    return true;
}

static void server_init(void)
{
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;
    config.lru_purge_enable = true;
    httpd_handle_t server = NULL;
    if (!check(httpd_start(&server, &config), "Page server failed")) return;
    const httpd_uri_t routes[] = {
        {.uri = "/", .method = HTTP_GET, .handler = page_handler},
        {.uri = "/status", .method = HTTP_GET, .handler = api_handler},
        {.uri = "/start", .method = HTTP_POST, .handler = api_handler, .user_ctx = "start"},
        {.uri = "/stop", .method = HTTP_POST, .handler = api_handler, .user_ctx = "stop"},
        {.uri = "/start", .method = HTTP_GET, .handler = api_handler, .user_ctx = "start"},
        {.uri = "/stop", .method = HTTP_GET, .handler = api_handler, .user_ctx = "stop"},
    };
    for (unsigned i = 0; i < sizeof(routes) / sizeof(routes[0]); i++) {
        if (!check(httpd_register_uri_handler(server, &routes[i]), "Page route failed")) return;
    }
}

void app_main(void)
{
    control_lock = xSemaphoreCreateMutex();
    events = xEventGroupCreate();
    if (!control_lock || !events) {
        ESP_LOGE(TAG, "Control allocation failed; advertising remains off");
        return;
    }
    ESP_LOGI(TAG, "Boot reset_reason=%d; running=false sent=0", esp_reset_reason());
    // never erase nvs automatically, even on version or full-page errors
    if (check(nvs_flash_init(), "NVS init failed; NVS left intact") && ap_init()) {
        server_init();
        bluetooth_init();
        check(esp_register_shutdown_handler(shutdown_stop), "Shutdown handler failed");
    }
    for (;;) {
        char json[512];
        status_json(json, sizeof(json));
        ESP_LOGI(TAG, "%s", json);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
