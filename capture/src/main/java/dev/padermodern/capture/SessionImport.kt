package dev.padermodern.capture

import java.io.File
import java.io.IOException
import java.io.InputStream
import java.time.Instant
import java.util.zip.ZipInputStream
import kotlinx.serialization.json.JsonObject

data class ImportResult(val sessionId: String, val redecoded: Int, val advertisements: Long)

// reimports a zip under a -p<version> id
object SessionImport {
    private val safeId = Regex("[A-Za-z0-9-]{1,80}")
    private val allowed = setOf("events.jsonl", "session.json", "profiles.json", "export.json")
    private const val MAX_BYTES = 256L * 1024 * 1024

    fun import(input: InputStream, root: File): ImportResult {
        val files = mutableMapOf<String, ByteArray>()
        var id: String? = null
        var total = 0L
        ZipInputStream(input).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                if (entry.isDirectory) continue
                val parts = entry.name.split('/')
                if (parts.size < 2 || !safeId.matches(parts[0])) throw IOException("Unerwarteter Eintrag ${entry.name}")
                if (id != null && id != parts[0]) throw IOException("ZIP enthält mehrere Sitzungen")
                id = parts[0]
                val name = parts.drop(1).joinToString("/")
                val known = name in allowed || parts.size == 3 && parts[1] == "lookups" && parts[2].matches(Regex("[A-Za-z0-9_.-]{1,80}"))
                if (!known) continue
                val bytes = zip.readBytes()
                total += bytes.size
                if (total > MAX_BYTES) throw IOException("ZIP ist zu groß")
                files[name] = bytes
            }
        }
        val original = id ?: throw IOException("Leeres ZIP")
        val events = files["events.jsonl"] ?: throw IOException("events.jsonl fehlt")
        val meta = files["session.json"]?.let { runCatching { CaptureJson.decodeFromString(SessionMeta.serializer(), it.decodeToString()) }.getOrNull() }
            ?: throw IOException("session.json fehlt oder ist unlesbar")

        val lines = events.decodeToString().split('\n').filter { it.isNotBlank() }
        val parsed = lines.map { CaptureJson.decodeFromString(Event.serializer(), it) }
        val redecoded = parsed.count { it.type == "advertisement" && advertisement(it).parserVersion < PARSER_VERSION }
        val sessionId = if (redecoded > 0) "${original.substringBefore("-p")}-p$PARSER_VERSION" else original
        val target = File(root, sessionId)
        if (target.exists()) throw IOException("Sitzung $sessionId ist schon vorhanden")

        val index = CaptureIndex()
        val out = StringBuilder()
        var ads = 0L
        parsed.forEach { e ->
            val data = if (e.type == "advertisement") {
                ads++
                CaptureJson.encodeToJsonElement(RawAd.serializer(), advertisement(e).redecoded()) as JsonObject
            } else e.data
            val event = e.copy(sessionId = sessionId, eventId = "$sessionId-${e.sequence}", data = data)
            out.append(CaptureJson.encodeToString(Event.serializer(), event)).append('\n')
            index.apply(event, Instant.parse(e.timestampUtc).toEpochMilli())
        }
        val bytes = out.toString().toByteArray()
        val staging = File(root, ".import-$sessionId").also { it.deleteRecursively(); it.mkdirs() }
        try {
            File(staging, "events.jsonl").writeBytes(bytes)
            files.filterKeys { it.startsWith("lookups/") }.forEach { (name, b) -> File(staging, name).also { it.parentFile?.mkdirs() }.writeBytes(b) }
            index.markUnfinishedOperations()
            File(staging, "profiles.json").writeText(profilesJson(index.snapshot()).toString())
            val updated = meta.copy(
                sessionId = sessionId, events = parsed.size.toLong(), advertisements = ads, bytes = bytes.size.toLong(),
                eventsSha256 = sha256(bytes), state = if (meta.state == "running") "interrupted" else meta.state,
                derivedFrom = original.takeIf { it != sessionId },
                importedUtc = Instant.now().toString(),
            )
            File(staging, "session.json").writeText(CaptureJson.encodeToString(SessionMeta.serializer(), updated))
            if (!staging.renameTo(target)) throw IOException("Sitzung konnte nicht gespeichert werden")
        } finally {
            staging.deleteRecursively()
        }
        return ImportResult(sessionId, redecoded, ads)
    }

    private fun advertisement(e: Event) = CaptureJson.decodeFromJsonElement(RawAd.serializer(), e.data)
}
