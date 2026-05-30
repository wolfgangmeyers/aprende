package com.magicalhippie.aprende.ui.settings

import android.app.Application
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.magicalhippie.aprende.data.backup.BackupCodec
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import javax.inject.Inject

/** One-shot result of a backup export/import action (drives a transient status banner). */
sealed interface BackupStatus {
    data object Idle : BackupStatus
    data object Working : BackupStatus
    data class Exported(val byteCount: Int) : BackupStatus
    data object Imported : BackupStatus
    data class Error(val message: String) : BackupStatus
}

data class BackupUiState(val status: BackupStatus = BackupStatus.Idle)

/**
 * Drives SAF-based progress backup/restore (SPEC §11, C3 / AC11). The screen owns the SAF
 * `CreateDocument`/`OpenDocument` launchers and hands the chosen [Uri] here; this VM streams
 * through the [android.content.ContentResolver] (no storage permission needed) and uses
 * [BackupCodec] for the versioned JSON.
 *
 * Export: `exportSnapshot()` → encode → write. Import: read → decode → `importSnapshot()`
 * (clear-then-insert). All DB/IO work runs off the main thread (`Dispatchers.IO`).
 */
@HiltViewModel
class BackupViewModel @Inject constructor(
    private val app: Application,
    private val progress: ProgressRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(BackupUiState())
    val uiState: StateFlow<BackupUiState> = _uiState.asStateFlow()

    /** Suggested filename for the export document. */
    val suggestedFileName: String get() = "aprende-progress-backup.json"

    fun export(target: Uri) {
        _uiState.value = BackupUiState(BackupStatus.Working)
        viewModelScope.launch {
            try {
                val json = withContext(Dispatchers.IO) {
                    val snapshot = progress.exportSnapshot()
                    BackupCodec.encode(snapshot)
                }
                val bytes = json.toByteArray(Charsets.UTF_8)
                withContext(Dispatchers.IO) {
                    app.contentResolver.openOutputStream(target, "w")?.use { it.write(bytes) }
                        ?: error("Could not open the chosen file for writing")
                }
                _uiState.value = BackupUiState(BackupStatus.Exported(bytes.size))
            } catch (t: Throwable) {
                _uiState.value = BackupUiState(BackupStatus.Error(t.message ?: "Export failed"))
            }
        }
    }

    fun import(source: Uri) {
        _uiState.value = BackupUiState(BackupStatus.Working)
        viewModelScope.launch {
            try {
                val text = withContext(Dispatchers.IO) {
                    app.contentResolver.openInputStream(source)?.use { it.readBytes().toString(Charsets.UTF_8) }
                        ?: error("Could not open the chosen file for reading")
                }
                withContext(Dispatchers.IO) {
                    val snapshot = BackupCodec.decode(text)
                    progress.importSnapshot(snapshot)
                }
                _uiState.value = BackupUiState(BackupStatus.Imported)
            } catch (t: Throwable) {
                _uiState.value = BackupUiState(BackupStatus.Error(t.message ?: "Import failed"))
            }
        }
    }
}
