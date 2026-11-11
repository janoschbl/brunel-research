/*
 * Brunel bus module emulator.
 *
 * A deliberately small BlueZ-5.78-shaped GATT peripheral.  The point is not
 * to emulate the whole stack; it is to reproduce the one thing that matters
 * for the exploit: the vendor 0x1f20 write handler copies an unbounded ATT
 * value into a 256 byte stack buffer.
 *
 * The process talks a line protocol on an inherited socket:
 *
 *   <- ATT <hex>          one raw ATT PDU
 *   <- GET <path>         read a file below the state directory
 *   <- BOOT               supervisor only: mark the module back online
 *   <- QUIT
 *   -> ATT <hex>          one raw ATT PDU (response)
 *   -> ADV <hex>          advertisement
 *   -> EV <kind> <text>   event (exec, crash, persist, ...)
 *
 * A supervisor owns the listening socket and restarts this process after a
 * crash, which is how a real vendor daemon is supervised.
 */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <setjmp.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/un.h>
#include <unistd.h>

#define BUF_SIZE 256
#define MAX_VALUE 512
#define MAX_PREPARED 4

/* ---------------------------------------------------------------- gatt db */

enum attr_kind { ATTR_SERVICE, ATTR_CHAR, ATTR_VALUE, ATTR_CCCD };

struct attr {
	uint16_t handle;
	enum attr_kind kind;
	uint8_t props;
	uint16_t uuid16;
	const uint8_t *value;
	size_t length;
};

static uint8_t route_value[96] =
	"Heinz NixdorfWendeschleife\x1dHauptbahnhof\x1d";
static size_t route_length = sizeof("Heinz NixdorfWendeschleife\x1dHauptbahnhof\x1d") - 1;
static uint8_t name_value[32] = "ivi";
static size_t name_length = 3;
static uint8_t pnp_value[7] = { 2, 0x6b, 0x1d, 0x46, 0x02, 0x4e, 0x05 };
static uint8_t cccd_value[2];
static uint8_t action_value[MAX_VALUE];
static size_t action_length;

static const struct attr attrs[] = {
	{ 0x0001, ATTR_SERVICE, 0, 0x1f1f, NULL, 0 },
	{ 0x0002, ATTR_CHAR, 0x08, 0x1f20, NULL, 0 },
	{ 0x0003, ATTR_VALUE, 0x08, 0x1f20, action_value, 0 },
	{ 0x0004, ATTR_SERVICE, 0, 0x201f, NULL, 0 },
	{ 0x0005, ATTR_CHAR, 0x02, 0x2020, NULL, 0 },
	{ 0x0006, ATTR_VALUE, 0x02, 0x2020, route_value, 0 },
	{ 0x0007, ATTR_SERVICE, 0, 0x1800, NULL, 0 },
	{ 0x0008, ATTR_CHAR, 0x02, 0x2a00, NULL, 0 },
	{ 0x0009, ATTR_VALUE, 0x02, 0x2a00, name_value, 0 },
	{ 0x000a, ATTR_SERVICE, 0, 0x180a, NULL, 0 },
	{ 0x000b, ATTR_CHAR, 0x02, 0x2a50, NULL, 0 },
	{ 0x000c, ATTR_VALUE, 0x02, 0x2a50, pnp_value, 0 },
	{ 0x000d, ATTR_SERVICE, 0, 0x1801, NULL, 0 },
	{ 0x000e, ATTR_CHAR, 0x20, 0x2a05, NULL, 0 },
	{ 0x000f, ATTR_VALUE, 0x00, 0x2902, cccd_value, 0 },
};
#define ATTR_COUNT (sizeof(attrs) / sizeof(attrs[0]))

/* ------------------------------------------------------------- the target */

/* Known address for the command bytes; the vulnerable copy also lands here. */
uint8_t action_shadow[MAX_VALUE] __attribute__((aligned(4)));

static sigjmp_buf resume;
static int handler_active;

void emu_continue(void)
{
	if (handler_active) {
		handler_active = 0;
		if (getenv("EMU_DEBUG"))
			dprintf(2, "emu_continue jump handler_active=1\n");
		siglongjmp(resume, 1);
	}
	if (getenv("EMU_DEBUG"))
		dprintf(2, "emu_continue exit handler_active=0\n");
	_exit(0);
}

static void emit(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static size_t hexcat(char *out, size_t used, const void *data, size_t length);
static char debug_line[128];

__attribute__((naked, noinline)) void pop_r0_r4_pc(void)
{
	__asm__ volatile("pop {r0, r4, pc}");
}

/* libc calls return through lr, so a chain that jumps into them must load it */
__attribute__((naked, noinline)) void pop_r0_lr_pc(void)
{
	__asm__ volatile("pop {r0, r4, lr}\n\tbx r4");
}

__attribute__((noinline, noclone)) void handle_action(const uint8_t *value, size_t len)
{
	char buf[BUF_SIZE];

	if (len > MAX_VALUE)
		len = MAX_VALUE;
	if (getenv("EMU_DEBUG") && len > 256)
		emit("EV chain %.*s",
		     (int) hexcat(debug_line, 0, value + 256,
				  len - 256 < 48 ? len - 256 : 48),
		     debug_line);
	memcpy(action_shadow, value, len);
	/* copy from the stable mirror: the ATT buffer may itself sit in the
	 * stack range this overflow is about to smash */
	memcpy(buf, action_shadow, len);
}

/* One byte 0x42 followed by a shell command: the persistence hook. */
__attribute__((noinline, noclone)) void backdoor(const uint8_t *value, size_t len)
{
	char command[MAX_VALUE];

	if (len > 1 && value[0] == 0x42) {
		memcpy(command, value + 1, len - 1);
		command[len - 1] = 0;
		system(command);
		emu_continue();
	}
	handle_action(value, len);
}

void (*action_write_cb)(const uint8_t *, size_t) = handle_action;

void set_action_cb(void *fn)
{
	action_write_cb = (void (*)(const uint8_t *, size_t))fn;
}

/* --------------------------------------------------------------- transport */

static int out_fd = 1;

static void emit(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

#include <stdarg.h>

static void emit(const char *fmt, ...)
{
	char line[4096];
	va_list ap;
	int n;

	va_start(ap, fmt);
	n = vsnprintf(line, sizeof(line) - 2, fmt, ap);
	va_end(ap);
	if (n < 0)
		return;
	if (n > (int) sizeof(line) - 2)
		n = (int) sizeof(line) - 2;
	line[n++] = '\n';
	{
		ssize_t wrote = write(out_fd, line, n);
		if (getenv("EMU_DEBUG"))
			dprintf(2, "emit fd=%d n=%d wrote=%zd errno=%d\n", out_fd, n, wrote, errno);
	}
}

static size_t hexcat(char *out, size_t used, const void *data, size_t length)
{
	static const char digits[] = "0123456789abcdef";
	const uint8_t *bytes = data;

	for (size_t i = 0; i < length; i++) {
		out[used++] = digits[bytes[i] >> 4];
		out[used++] = digits[bytes[i] & 0x0f];
	}
	return used;
}

static int hexval(int c){
	if (c >= '0' && c <= '9')
		return c - '0';
	if (c >= 'a' && c <= 'f')
		return c - 'a' + 10;
	if (c >= 'A' && c <= 'F')
		return c - 'A' + 10;
	return -1;
}

static size_t unhex(const char *text, uint8_t *out, size_t max)
{
	size_t n = 0;

	while (text[0] && text[1] && n < max) {
		int hi = hexval(text[0]);
		int lo = hexval(text[1]);
		if (hi < 0 || lo < 0)
			break;
		out[n++] = (uint8_t) ((hi << 4) | lo);
		text += 2;
	}
	return n;
}

static void att_error(uint8_t request, uint16_t handle, uint8_t reason)
{
	emit("ATT 01%02x%02x%02x%02x",
	     request, handle & 0xff, handle >> 8, reason);
}

static struct attr *find_attr(uint16_t handle)
{
	for (size_t i = 0; i < ATTR_COUNT; i++)
		if (attrs[i].handle == handle)
			return (struct attr *) &attrs[i];
	return NULL;
}

static void update_action_value(const uint8_t *value, size_t len)
{
	if (len > MAX_VALUE)
		len = MAX_VALUE;
	memcpy(action_value, value, len);
	action_length = len;
}

static void call_handler(const uint8_t *value, size_t len)
{
	handler_active = 1;
	action_write_cb(value, len);
	handler_active = 0;
}

struct prepared_slot {
	uint16_t handle;
	uint16_t offset;
	uint8_t value[MAX_VALUE];
	size_t length;
};

static struct prepared_slot prepared_slots[MAX_PREPARED];
static size_t prepared_count;
static void execute_prepared(void);

static void write_attr(struct attr *attr, const uint8_t *value, size_t len)
{
	switch (attr->handle) {
	case 0x0003:
		update_action_value(value, len);
		emit("EV action length=%zu", len);
		call_handler(value, len);
		break;
	case 0x0009:
		if (len > sizeof(name_value))
			len = sizeof(name_value);
		memcpy(name_value, value, len);
		name_length = len;
		emit("EV name %.*s", (int) len, value);
		break;
	case 0x000f:
		if (len >= 2)
			memcpy(cccd_value, value, 2);
		break;
	default:
		break;
	}
}

static void handle_att(const uint8_t *pdu, size_t len)
{
	uint16_t start, end, handle;
	uint8_t opcode;

	if (len < 1)
		return;
	opcode = pdu[0];
	if (getenv("EMU_DEBUG"))
		dprintf(2, "att op=%02x len=%zu\n", opcode, len);

	switch (opcode) {
	case 0x02: { /* MTU exchange */
		uint16_t mtu = len >= 3 ? (uint16_t) (pdu[1] | (pdu[2] << 8)) : 23;
		if (mtu < 23)
			mtu = 23;
		if (mtu > 517)
			mtu = 517;
		emit("ATT 03%02x%02x", mtu & 0xff, mtu >> 8);
		break;
	}
	case 0x04: { /* find information */
		char body[2048];
		size_t used = 0;
		int found = 0;
		if (len < 5)
			return att_error(0x04, 0, 0x0a);
		start = (uint16_t) (pdu[1] | (pdu[2] << 8));
		end = (uint16_t) (pdu[3] | (pdu[4] << 8));
		for (size_t i = 0; i < ATTR_COUNT && used < sizeof(body) - 8; i++) {
			if (attrs[i].handle < start || attrs[i].handle > end)
				continue;
			used += (size_t) snprintf(body + used, sizeof(body) - used,
						  "%02x%02x00%02x%02x",
						  attrs[i].handle & 0xff,
						  attrs[i].handle >> 8,
						  attrs[i].uuid16 & 0xff,
						  attrs[i].uuid16 >> 8);
			found = 1;
		}
		if (!found)
			return att_error(0x04, start, 0x0a);
		emit("ATT 05%s", body);
		break;
	}
	case 0x08: { /* read by type */
		uint8_t body[2048];
		size_t used = 0;
		int found = 0;
		if (len < 7)
			return att_error(0x08, 0, 0x0a);
		start = (uint16_t) (pdu[1] | (pdu[2] << 8));
		end = (uint16_t) (pdu[3] | (pdu[4] << 8));
		if (pdu[5] != 0x03 || pdu[6] != 0x28)
			return att_error(0x08, start, 0x0a);
		for (size_t i = 0; i < ATTR_COUNT; i++) {
			uint16_t value_handle;
			uint8_t entry[7];

			if (attrs[i].kind != ATTR_CHAR)
				continue;
			if (attrs[i].handle < start || attrs[i].handle > end)
				continue;
			value_handle = attrs[i].handle + 1;
			entry[0] = attrs[i].handle & 0xff;
			entry[1] = attrs[i].handle >> 8;
			entry[2] = attrs[i].props;
			entry[3] = value_handle & 0xff;
			entry[4] = value_handle >> 8;
			entry[5] = attrs[i].uuid16 & 0xff;
			entry[6] = attrs[i].uuid16 >> 8;
			used = hexcat((char *) body, used, entry, sizeof(entry));
			found = 1;
		}
		if (!found)
			return att_error(0x08, start, 0x0a);
		emit("ATT 09%.*s", (int) used, (char *) body);
		break;
	}
	case 0x0a: { /* read */
		struct attr *attr;
		char body[1100];
		size_t used = 0;

		if (len < 3)
			return att_error(0x0a, 0, 0x0a);
		handle = (uint16_t) (pdu[1] | (pdu[2] << 8));
		attr = find_attr(handle);
		if (!attr || !(attr->props & 0x02))
			return att_error(0x0a, handle, 0x0a);
		if (attr->kind == ATTR_VALUE && attr->handle == 0x0006)
			used = hexcat(body, used, route_value, route_length);
		else if (attr->kind == ATTR_VALUE && attr->handle == 0x0009)
			used = hexcat(body, used, name_value, name_length);
		else if (attr->kind == ATTR_VALUE && attr->handle == 0x000c)
			used = hexcat(body, used, pnp_value, 7);
		else if (attr->kind == ATTR_VALUE && attr->handle == 0x0003)
			used = hexcat(body, used, action_value, action_length);
		emit("ATT 0b%.*s", (int) used, body);
		break;
	}
	case 0x10: { /* read by group type */
		uint8_t body[1024];
		size_t used = 0;
		int found = 0;
		if (len < 7)
			return att_error(0x10, 0, 0x0a);
		start = (uint16_t) (pdu[1] | (pdu[2] << 8));
		end = (uint16_t) (pdu[3] | (pdu[4] << 8));
		if (pdu[5] != 0x00 || pdu[6] != 0x28)
			return att_error(0x10, start, 0x0a);
		for (size_t i = 0; i < ATTR_COUNT; i++) {
			size_t j;
			uint16_t group_end;
			uint8_t entry[6];

			if (attrs[i].kind != ATTR_SERVICE)
				continue;
			if (attrs[i].handle < start || attrs[i].handle > end)
				continue;
			for (j = i + 1; j < ATTR_COUNT; j++)
				if (attrs[j].kind == ATTR_SERVICE)
					break;
			group_end = attrs[j - 1].handle;
			entry[0] = attrs[i].handle & 0xff;
			entry[1] = attrs[i].handle >> 8;
			entry[2] = group_end & 0xff;
			entry[3] = group_end >> 8;
			entry[4] = attrs[i].uuid16 & 0xff;
			entry[5] = attrs[i].uuid16 >> 8;
			used = hexcat((char *) body, used, entry, sizeof(entry));
			found = 1;
		}
		if (!found)
			return att_error(0x10, start, 0x0a);
		emit("ATT 11%.*s", (int) used, (char *) body);
		break;
	}
	case 0x12: { /* write request */
		struct attr *attr;
		if (len < 3)
			return att_error(0x12, 0, 0x0a);
		handle = (uint16_t) (pdu[1] | (pdu[2] << 8));
		attr = find_attr(handle);
		if (!attr || !(attr->props & 0x08))
			return att_error(0x12, handle, 0x03);
		write_attr(attr, pdu + 3, len - 3);
		emit("ATT 13");
		break;
	}
	case 0x52: { /* write command */
		struct attr *attr;
		if (len < 3)
			return;
		handle = (uint16_t) (pdu[1] | (pdu[2] << 8));
		attr = find_attr(handle);
		if (!attr || !(attr->props & 0x0c))
			return;
		write_attr(attr, pdu + 3, len - 3);
		break;
	}
	case 0x16: { /* prepare write */
		uint16_t offset;
		size_t slot = MAX_PREPARED;
		uint8_t body[1100];

		if (len < 5)
			return att_error(0x16, 0, 0x0a);
		handle = (uint16_t) (pdu[1] | (pdu[2] << 8));
		offset = (uint16_t) (pdu[3] | (pdu[4] << 8));
		if (!find_attr(handle))
			return att_error(0x16, handle, 0x0a);
		if (offset + (len - 5) > MAX_VALUE)
			return att_error(0x16, handle, 0x0b);
		for (size_t i = 0; i < prepared_count; i++)
			if (prepared_slots[i].handle == handle)
				slot = i;
		if (slot == MAX_PREPARED) {
			if (prepared_count == MAX_PREPARED)
				return att_error(0x16, handle, 0x0b);
			slot = prepared_count++;
			prepared_slots[slot].handle = handle;
			prepared_slots[slot].offset = 0;
			prepared_slots[slot].length = 0;
		}
		if (offset > prepared_slots[slot].length)
			return att_error(0x16, handle, 0x07);
		memcpy(prepared_slots[slot].value + offset, pdu + 5, len - 5);
		if (offset + (len - 5) > prepared_slots[slot].length)
			prepared_slots[slot].length = offset + (len - 5);
		emit("ATT 17%02x%02x%02x%02x%.*s",
		     pdu[1], pdu[2], pdu[3], pdu[4],
		     (int) hexcat((char *) body, 0, pdu + 5, len - 5), (char *) body);
		break;
	}
	case 0x18: /* execute write */
		execute_prepared();
		emit("ATT 19");
		break;
	case 0x1e:
		break;
	default:
		att_error(opcode, 0, 0x06);
		break;
	}
}

static void execute_prepared(void)
{
	for (size_t i = 0; i < prepared_count; i++) {
		struct attr *attr = find_attr(prepared_slots[i].handle);
		if (attr)
			write_attr(attr, prepared_slots[i].value, prepared_slots[i].length);
	}
	prepared_count = 0;
}

/* ------------------------------------------------------------------ state */

static const char *state_dir;

static int read_file(const char *name, uint8_t *out, size_t max)
{
	char path[512];
	int fd;
	ssize_t n;

	snprintf(path, sizeof(path), "%s/%s", state_dir, name);
	fd = open(path, O_RDONLY);
	if (fd < 0)
		return -1;
	n = read(fd, out, max);
	close(fd);
	return n < 0 ? -1 : (int) n;
}

static void load_state(void)
{
	uint8_t buffer[256];
	int n;

	n = read_file("name", buffer, sizeof(buffer));
	if (n > 0) {
		if ((size_t) n > sizeof(name_value))
			n = sizeof(name_value);
		memcpy(name_value, buffer, (size_t) n);
		name_length = (size_t) n;
	}
	n = read_file("route", buffer, sizeof(buffer));
	if (n > 0) {
		if ((size_t) n > sizeof(route_value))
			n = sizeof(route_value);
		memcpy(route_value, buffer, (size_t) n);
		route_length = (size_t) n;
	}
	if (read_file("persist", buffer, 1) >= 0)
		action_write_cb = backdoor;
}

static void load_canary(void)
{
	extern uintptr_t __stack_chk_guard;
	const char *value = getenv("EMU_CANARY");
	if (value)
		__stack_chk_guard = (uintptr_t) strtoul(value, NULL, 16);
}

/* ------------------------------------------------------------------- main */

static char *line_buffer;
static size_t line_length;

static int read_line(int fd, char *out, size_t max)
{
	while (1) {
		char *newline = memchr(line_buffer, '\n', line_length);
		if (newline) {
			size_t n = (size_t) (newline - line_buffer);
			if (n >= max)
				n = max - 1;
			memcpy(out, line_buffer, n);
			out[n] = 0;
			memmove(line_buffer, newline + 1,
				line_length - (size_t) (newline - line_buffer) - 1);
			line_length -= (size_t) (newline - line_buffer) + 1;
			return (int) n;
		}
		ssize_t got = read(fd, line_buffer + line_length,
				   4096 - line_length);
		if (got <= 0)
			return -1;
		line_length += (size_t) got;
	}
}

static char serve_line[8192];
static uint8_t serve_pdu[1024];
static int serve_fd_handle;

static void serve_fd(int fd)
{
	out_fd = fd;
	serve_fd_handle = fd;
	line_length = 0;
	while (read_line(serve_fd_handle, serve_line, sizeof(serve_line)) >= 0) {
		if (!strncmp(serve_line, "ATT ", 4)) {
			size_t n = unhex(serve_line + 4, serve_pdu, sizeof(serve_pdu));
			if (n)
				handle_att(serve_pdu, n);
		} else if (!strncmp(serve_line, "GET ", 4)) {
			uint8_t data[4096];
			int n = read_file(serve_line + 4, data, sizeof(data));
			if (n < 0)
				emit("EV get-miss %s", serve_line + 4);
			else
				emit("DATA %s %.*s", serve_line + 4, n, (char *) data);
		} else if (!strncmp(serve_line, "EXEC ", 5)) {
			emit("EV exec-begin");
			system(serve_line + 5);
			emit("EV exec-end");
		} else if (!strncmp(serve_line, "QUIT", 4)) {
			break;
		}
	}
}

int main(int argc, char **argv)
{
	int fd = 0;
	const char *listen_path = NULL;
	const char *env;
	char pid_text[16];

	for (int i = 1; i < argc; i++) {
		if (!strcmp(argv[i], "--fd") && i + 1 < argc)
			fd = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--listen") && i + 1 < argc)
			listen_path = argv[++i];
		else if (!strcmp(argv[i], "--state") && i + 1 < argc)
			state_dir = argv[++i];
	}
	if (!state_dir)
		state_dir = getenv("EMU_STATE") ? getenv("EMU_STATE") : ".";
	signal(SIGPIPE, SIG_IGN);
	load_canary();
	load_state();
	env = getenv("EMU_CANARY");
	snprintf(pid_text, sizeof(pid_text), "%d", (int) getpid());
	setenv("TARGET_PID", pid_text, 1);
	setenv("EMU_STATE", state_dir, 1);

	line_buffer = malloc(4096);
	if (!line_buffer)
		return 1;

	if (listen_path) {
		struct sockaddr_un address;
		int listener;
		int client = -1;

		unlink(listen_path);
		listener = socket(AF_UNIX, SOCK_STREAM, 0);
		if (listener < 0)
			return 1;
		memset(&address, 0, sizeof(address));
		address.sun_family = AF_UNIX;
		strncpy(address.sun_path, listen_path, sizeof(address.sun_path) - 1);
		if (bind(listener, (struct sockaddr *) &address, sizeof(address)) < 0)
			return 1;
		listen(listener, 4);
		/* Tell the supervisor the listener is ready before accepting. */
		write(2, "ready\n", 6);
		for (;;) {
			if (client < 0) {
				client = accept(listener, NULL, NULL);
				if (client < 0)
					continue;
				if (getenv("EMU_DEBUG"))
					dprintf(2, "accept fd=%d\n", client);
			}
			/* The overflow smashes every frame between here and the
			 * handler, so the resume anchor lives in this loop and the
			 * serve frame is simply rebuilt after a longjmp. */
			if (sigsetjmp(resume, 1) == 0) {
				serve_fd(client);
				if (getenv("EMU_DEBUG"))
					dprintf(2, "eof fd=%d\n", client);
				close(client);
				client = -1;
			}
			if (getenv("EMU_DEBUG"))
				dprintf(2, "resumed, handler_active=%d\n", handler_active);
			handler_active = 0;
			prepared_count = 0;
		}
	}

	out_fd = fd;
	emit("HELLO pid=%d", (int) getpid());
	serve_fd(fd);
	return 0;
}
