// 256-byte stack buffer, saved rip at offset 264
#include <stdint.h>
#include <string.h>

char action_command[64] = "echo PWNED-GATT";

__attribute__((naked, noinline)) void pop_rdi_ret(void)
{
	__asm__ volatile("pop %rdi; ret");
}

__attribute__((noinline, noclone)) void handle_action(const uint8_t *value, size_t len)
{
	char buf[256];

	memcpy(buf, value, len);
}
