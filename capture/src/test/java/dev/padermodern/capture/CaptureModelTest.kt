package dev.padermodern.capture

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CaptureModelTest {
    private fun hex(s: String) = s.chunked(2).map { it.toInt(16).toByte() }.toByteArray()

    private val good = hex("02010603031f1f13ff787d00100504" + "0100" + "0b00" + "6600" + "6812" + "0800" + "0001")

    @Test fun decodesProtocol16() {
        val d = decodeBus(parseStructures(good))
        assertEquals("ok", d.result)
        assertEquals(1, d.lineId); assertEquals(11, d.destinationId); assertEquals(102, d.nextStopId)
        assertEquals(0x1268, d.hardwareId); assertEquals(8, d.course); assertEquals("0001", d.unknownHex)
    }

    @Test fun keepsPacketsThatFailToParse() {
        val truncated = hex("02010603031f1f06ff787d001005")
        val s = parseStructures(truncated)
        assertEquals("Service 0x1f1f", candidateReason(s))
        assertEquals("too_short", decodeBus(s).result)
        assertEquals("no_manufacturer", decodeBus(parseStructures(hex("02010603031f1f"))).result)
    }

    @Test fun flagsOtherProtocolsWithoutDroppingFields() {
        val other = good.copyOf().also { it[12] = 0x11 }
        val d = decodeBus(parseStructures(other))
        assertEquals("unknown_protocol", d.result)
        assertEquals(17, d.protocol); assertEquals(0x1268, d.hardwareId)
    }

    // line 8 to neuenbeken from the 24 october 2026 field log
    private val line8 = hex("13ff787d001213e121040101803800000000000002010603031f1f0409697669")

    @Test fun decodesProtocol18LineText() {
        val d = decodeBus(parseStructures(line8))
        assertEquals("ok", d.result); assertEquals(18, d.protocol); assertEquals("8", d.lineText); assertEquals(3, d.dataVersion)
        assertNull(d.lineId); assertNull(d.hardwareId); assertEquals("e121040101", d.unknownHex)
        assertEquals("unknown_protocol", decodeBus(parseStructures(line8.copyOf().also { it[13] = 0 })).result)
    }

    @Test fun readsVehicleTextFromGatt() {
        val v = vehicleText("4e6575656e62656b656e486f6c7467726576656e73747261c39f651d52617468617573706c61747a1d")!!
        assertEquals("NeuenbekenHoltgrevenstraße", v.destination); assertEquals("Rathausplatz", v.nextStop)
        assertNull(vehicleText("4e65"))
    }

    @Test fun ignoresUnrelatedDevices() {
        assertNull(candidateReason(parseStructures(hex("020106030318 0f".replace(" ", "")))))
        assertTrue(profileIdOf("s", "AA").startsWith("p-"))
    }
}
