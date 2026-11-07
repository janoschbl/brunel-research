#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "lib/bluetooth.h"
#include "lib/uuid.h"
#include "src/shared/att-types.h"
#include "src/shared/gatt-db.h"
#include "src/shared/util.h"

static void found(struct gatt_db_attribute *attribute, void *user_data)
{
	unsigned int *count = user_data;
	(*count)++;
}

int main(void)
{
	struct gatt_db *db = gatt_db_new();
	bt_uuid_t uuid;
	struct gatt_db_attribute *service;
	unsigned int count;
	uint16_t ranges[][2] = {
		{ 0x0001, 0xFFFF }, { 0xFFFF, 0xFFFF }, { 0x0000, 0x0000 },
		{ 0x0010, 0x0001 }, { 0x0001, 0x0001 }, { 0x0002, 0x0003 },
	};

	bt_uuid16_create(&uuid, 0x1800);
	service = gatt_db_add_service(db, &uuid, true, 4);
	bt_uuid16_create(&uuid, 0x2A00);
	gatt_db_service_add_characteristic(service, &uuid,
					   BT_ATT_PERM_READ, BT_GATT_CHRC_PROP_READ,
					   NULL, NULL, NULL);
	gatt_db_service_set_active(service, true);

	for (size_t i = 0; i < sizeof(ranges) / sizeof(ranges[0]); i++) {
		count = 0;
		bt_uuid16_create(&uuid, 0x2803);
		gatt_db_find_by_type(db, ranges[i][0], ranges[i][1], &uuid, found, &count);
		gatt_db_find_by_type_value(db, ranges[i][0], ranges[i][1], &uuid,
					   NULL, 0, found, &count);
		gatt_db_read_by_type(db, ranges[i][0], ranges[i][1], uuid, NULL);
		printf("range %04x-%04x count=%u\n", ranges[i][0], ranges[i][1], count);
	}

	gatt_db_unref(db);
	return 0;
}
