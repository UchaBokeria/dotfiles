package dev.opencode.remote.chat

import android.content.Context
import android.graphics.BitmapFactory
import android.graphics.Bitmap
import android.net.Uri
import java.io.ByteArrayOutputStream

/** Staged attachment (H2): content resolved lazily at send time. */
data class StagedAttachment(
    val id: String,
    val uri: String,
    val filename: String,
    val mime: String,
    val sizeBytes: Long,
)

data class ResolvedAttachment(
    val filename: String,
    val mime: String,
    val dataUrl: String,
)

/**
 * Pure staging helpers (unit-tested). Compression policy (settings):
 * quality 0 = original bytes; 1 = JPEG q85 maxDim; 2 = JPEG q70 maxDim.
 */
object Attachments {

    fun isImage(mime: String): Boolean = mime.startsWith("image/")

    fun targetDim(maxDim: Int): Int = maxDim.coerceIn(320, 4096)

    fun jpegQuality(quality: Int): Int = when (quality) {
        1 -> 85
        2 -> 70
        else -> 70
    }

    fun buildDataUrl(mime: String, bytes: ByteArray): String =
        "data:$mime;base64," + java.util.Base64.getEncoder().encodeToString(bytes)

    /** Downscale + JPEG-encode. Returns null when the source can't be decoded. */
    fun compressImage(src: ByteArray, maxDim: Int, quality: Int): ByteArray? {
        return try {
        val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(src, 0, src.size, opts)
        if (opts.outWidth <= 0 || opts.outHeight <= 0) return null
        var sample = 1
        val longest = maxOf(opts.outWidth, opts.outHeight)
        while (longest / sample > maxDim) sample *= 2
        val decode = BitmapFactory.Options().apply { inSampleSize = sample }
        val bmp = BitmapFactory.decodeByteArray(src, 0, src.size, decode) ?: return null
        val scaled = if (maxOf(bmp.width, bmp.height) > maxDim) {
            val f = maxDim.toFloat() / maxOf(bmp.width, bmp.height)
            Bitmap.createScaledBitmap(bmp, (bmp.width * f).toInt(), (bmp.height * f).toInt(), true)
        } else bmp
        val out = ByteArrayOutputStream()
        scaled.compress(Bitmap.CompressFormat.JPEG, jpegQuality(quality), out)
        if (scaled !== bmp) bmp.recycle()
        out.toByteArray()
    } catch (_: Exception) {
        null
    }
    }
}

/** Resolve a staged attachment to a sendable data-URL part (IO thread). */
fun resolveAttachment(
    ctx: Context,
    att: StagedAttachment,
    quality: Int,
    maxDim: Int,
    maxBytes: Long,
): ResolvedAttachment? {
    if (att.sizeBytes > maxBytes && !Attachments.isImage(att.mime)) return null
    val uri = Uri.parse(att.uri) ?: return null
    val src = ctx.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return null
    if (src.size > maxBytes * 4) return null // sanity: never stage absurd blobs
    val mime = att.mime.ifBlank { "application/octet-stream" }
    val bytes = if (Attachments.isImage(mime) && quality > 0) {
        Attachments.compressImage(src, Attachments.targetDim(maxDim), quality)
            ?: return null
    } else src
    if (bytes.size > maxBytes) return null
    val finalMime = if (Attachments.isImage(mime) && quality > 0) "image/jpeg" else mime
    return ResolvedAttachment(att.filename, finalMime, Attachments.buildDataUrl(finalMime, bytes))
}
