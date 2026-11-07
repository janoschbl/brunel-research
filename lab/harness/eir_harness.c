#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "src/eir.h"

int main(int argc, char **argv)
{
	uint8_t data[255];
	int name_len = argc > 1 ? atoi(argv[1]) : 253;
	struct eir_data eir;

	if (name_len < 1 || name_len > 253) {
		fprintf(stderr, "name length must be 1..253\n");
		return 2;
	}

	data[0] = (uint8_t)(name_len + 1);
	data[1] = 0x09;
	memset(data + 2, 0xff, (size_t)name_len);

	memset(&eir, 0, sizeof(eir));
	eir_parse(&eir, data, (uint8_t)(name_len + 2));
	printf("name_len=%d parsed_len=%zu name=%.32s\n", name_len,
	       eir.name ? strlen(eir.name) : 0, eir.name ? eir.name : "");
	eir_data_free(&eir);
	return 0;
}
