package dev.opencode.remote.chat

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import java.io.File
import java.util.UUID

/** Query display name/size/mime for a content Uri. */
fun describeUri(ctx: Context, uri: Uri): Triple<String, String, Long> {
    var name = "file"
    var size = -1L
    ctx.contentResolver.query(uri, null, null, null, null)?.use { c ->
        if (c.moveToFirst()) {
            c.getColumnIndex(OpenableColumns.DISPLAY_NAME).takeIf { it >= 0 }?.let {
                name = c.getString(it) ?: name
            }
            c.getColumnIndex(OpenableColumns.SIZE).takeIf { it >= 0 }?.let {
                size = c.getLong(it)
            }
        }
    }
    val mime = ctx.contentResolver.getType(uri) ?: ""
    return Triple(name, mime, size)
}

/** H2: attach sheet + pickers + camera wiring. Calls onStage for every picked item. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AttachSheet(
    onDismiss: () -> Unit,
    onStage: (StagedAttachment) -> Unit,
) {
    val ctx = LocalContext.current
    var pendingCameraUri by remember { mutableStateOf<Uri?>(null) }

    fun stage(uri: Uri) {
        val (name, mime, size) = describeUri(ctx, uri)
        // Persist read permission for later resolve at send time.
        try {
            ctx.contentResolver.takePersistableUriPermission(
                uri, android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION,
            )
        } catch (_: Exception) {
            // TakePicture/file URIs don't need persisting.
        }
        onStage(StagedAttachment(UUID.randomUUID().toString(), uri.toString(), name, mime, size))
        onDismiss()
    }

    val pickImage = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia(),
    ) { uri -> if (uri != null) stage(uri) }
    val pickFile = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri -> if (uri != null) stage(uri) }
    val takePicture = rememberLauncherForActivityResult(
        ActivityResultContracts.TakePicture(),
    ) { ok ->
        if (ok) pendingCameraUri?.let { stage(it) }
        pendingCameraUri = null
    }
    val requestCamera = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) {
            val file = File(ctx.cacheDir, "cam-${UUID.randomUUID()}.jpg")
            val uri = FileProvider.getUriForFile(ctx, ctx.packageName + ".files", file)
            pendingCameraUri = uri
            takePicture.launch(uri)
        }
    }

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Attach", style = MaterialTheme.typography.titleMedium)
            SheetRow("📷 Take photo") {
                requestCamera.launch(android.Manifest.permission.CAMERA)
            }
            SheetRow("🖼 Choose image") {
                try {
                    pickImage.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
                } catch (_: Exception) {
                    pickFile.launch(arrayOf("image/*"))
                }
            }
            SheetRow("📎 Choose file") {
                pickFile.launch(arrayOf("*/*"))
            }
        }
    }
}

@Composable
private fun SheetRow(label: String, onClick: () -> Unit) {
    TextButton(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth()) { Text(label) }
    }
}

/** Staged chips above the composer (filename + size + remove). */
@Composable
fun StagedChips(
    staged: List<StagedAttachment>,
    onRemove: (String) -> Unit,
) {
    if (staged.isEmpty()) return
    Column(Modifier.fillMaxWidth().padding(horizontal = 8.dp)) {
        staged.forEach { att ->
            Row(
                Modifier.fillMaxWidth().padding(vertical = 2.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    "📎 ${att.filename}" + (if (att.sizeBytes >= 0) " (${att.sizeBytes / 1024} KB)" else ""),
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    "✕",
                    modifier = Modifier.clickable { onRemove(att.id) }.padding(4.dp),
                )
            }
        }
    }
}
