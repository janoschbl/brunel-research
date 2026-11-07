#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "payload.h"

int main(void)
{
    const uint8_t prefix[] = {0x02, 0x01, 0x06, 0x03, 0x03, 0x1f, 0x1f, 0xfb, 0x09};
    assert(sizeof(buscheck_payload) == 259);
    assert(memcmp(buscheck_payload, prefix, sizeof(prefix)) == 0);
    for (size_t i = sizeof(prefix); i < sizeof(buscheck_payload); ++i) {
        assert(buscheck_payload[i] == 0xff);
    }
    size_t offset = 0, fields = 0;
    while (offset < sizeof(buscheck_payload)) {
        assert(buscheck_payload[offset] > 0);
        offset += 1 + buscheck_payload[offset];
        assert(offset <= sizeof(buscheck_payload));
        fields++;
    }
    assert(offset == 259 && fields == 3);
    puts("PASS: 259 fixed bytes, exact prefix, 250 ff name bytes, three complete AD fields");
}
