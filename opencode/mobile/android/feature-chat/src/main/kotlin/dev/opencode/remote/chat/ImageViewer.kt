package dev.opencode.remote.chat

import android.content.Intent
import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.FileProvider
import java.io.File

/** Decode a `data:<mime>;base64,...` URL to bytes (null when not a data URL). */
fun dataUrlBytes(url: String): ByteArray? {
    val marker = ";base64,"
    val i = url.indexOf(marker)
    if (!url.startsWith("data:") || i < 0) return null
    return try {
        java.util.Base64.getDecoder().decode(url.substring(i + marker.length))
    } catch (_: Exception) {
        null
    }
}

private fun isImageMime(mime: String, url: String): Boolean =
    mime.startsWith("image/") || url.startsWith("data:image/")

/** H2 thread file part: image thumb (tap → viewer) or file card. */
@Composable
fun FilePartView(mime: String, filename: String, url: String) {
    var viewer by remember { mutableStateOf(false) }
    val bytes = remember(url) { if (isImageMime(mime, url)) dataUrlBytes(url) else null }
    val bmp = remember(bytes) {
        bytes?.let {
            try {
                BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap()
            } catch (_: Exception) {
                null
            }
        }
    }
    if (bmp != null) {
        Image(
            bitmap = bmp,
            contentDescription = filename,
            modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
                .clickable { viewer = true },
        )
    } else {
        Text("📎 $filename ($mime)")
    }
    if (viewer && bmp != null) {
        ImageViewer(filename = filename, bitmapBytes = bytes, onDismiss = { viewer = false })
    }
}

/** P3 basic viewer: pinch-zoom + share via system sheet. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ImageViewer(filename: String, bitmapBytes: ByteArray?, onDismiss: () -> Unit) {
    val ctx = LocalContext.current
    var scale by remember { mutableStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    val transform = rememberTransformableState { zoom, pan, _ ->
        scale = (scale * zoom).coerceIn(0.5f, 5f)
        offset += pan
    }
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Card(Modifier.fillMaxSize().padding(8.dp)) {
            val bmp = remember(bitmapBytes) {
                bitmapBytes?.let {
                    try {
                        BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap()
                    } catch (_: Exception) {
                        null
                    }
                }
            }
            if (bmp != null) {
                Image(
                    bitmap = bmp,
                    contentDescription = filename,
                    modifier = Modifier.weight(1f).fillMaxWidth()
                        .graphicsLayer(scaleX = scale, scaleY = scale, translationX = offset.x, translationY = offset.y)
                        .transformable(transform),
                )
            }
            TextButton(onClick = {
                bitmapBytes?.let { bytes ->
                    val file = File(ctx.cacheDir, "share-$filename")
                    file.writeBytes(bytes)
                    val uri = FileProvider.getUriForFile(ctx, ctx.packageName + ".files", file)
                    ctx.startActivity(
                        Intent(Intent.ACTION_SEND).apply {
                            type = "image/*"
                            putExtra(Intent.EXTRA_STREAM, uri)
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        },
                    )
                }
            }) { Text("Share") }
            TextButton(onClick = onDismiss) { Text("Close") }
        }
    }
}
