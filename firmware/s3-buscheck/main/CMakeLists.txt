idf_component_register(SRCS "buscheck.c"
    INCLUDE_DIRS "."
    REQUIRES bt esp_wifi esp_netif esp_event esp_http_server nvs_flash json
    EMBED_TXTFILES "index.html")
