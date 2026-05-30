package com.magicalhippie.aprende.ui.settings

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.magicalhippie.aprende.ui.theme.AprendeTheme

/**
 * Backup/restore screen (SPEC §11, C3 / AC11). Uses the Storage Access Framework — NO storage
 * permission required: `CreateDocument("application/json")` to pick an export target and
 * `OpenDocument()` to pick a file to import. The chosen `Uri` is handed to [BackupViewModel],
 * which streams via `ContentResolver` and (de)serializes with the versioned `BackupCodec`.
 */
@Composable
fun BackupScreen(viewModel: BackupViewModel = hiltViewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    // SAF export: CreateDocument returns the user-chosen target Uri (null if cancelled).
    val exportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/json"),
    ) { uri -> uri?.let(viewModel::export) }

    // SAF import: OpenDocument returns the chosen file Uri (we accept JSON mime types).
    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri -> uri?.let(viewModel::import) }

    BackupContent(
        state = state,
        onExportClick = { exportLauncher.launch(viewModel.suggestedFileName) },
        onImportClick = { importLauncher.launch(arrayOf("application/json", "text/json", "*/*")) },
    )
}

/** Stateless, preview- and test-friendly content. */
@Composable
fun BackupContent(
    state: BackupUiState,
    onExportClick: () -> Unit = {},
    onImportClick: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            text = "✨ Backup & restore",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.primary,
        )
        Text(
            "Export your progress to a file you control, then import it on a new phone. " +
                "No account, no internet required.",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(8.dp))
        Button(onClick = onExportClick, modifier = Modifier.fillMaxWidth()) { Text("Export progress") }
        Button(onClick = onImportClick, modifier = Modifier.fillMaxWidth()) { Text("Import progress") }

        val message = when (val s = state.status) {
            BackupStatus.Idle -> ""
            BackupStatus.Working -> "Working…"
            is BackupStatus.Exported -> "Exported ${s.byteCount} bytes ✨"
            BackupStatus.Imported -> "Progress restored ✨"
            is BackupStatus.Error -> "Error: ${s.message}"
        }
        if (message.isNotEmpty()) {
            Text(message, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun BackupPreview() {
    AprendeTheme {
        BackupContent(state = BackupUiState(BackupStatus.Exported(2048)))
    }
}
