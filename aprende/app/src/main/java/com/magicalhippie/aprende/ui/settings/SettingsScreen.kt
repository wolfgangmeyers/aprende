package com.magicalhippie.aprende.ui.settings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.magicalhippie.aprende.ui.theme.AprendeTheme

/**
 * Settings / About hub (SPEC §11/§4.5, P1.8). The two entries the spec requires for v1: the SAF
 * backup/restore screen and the content credits/attribution screen. Stateless — pure navigation
 * callbacks — so it needs no ViewModel.
 */
@Composable
fun SettingsScreen(
    onBackup: () -> Unit = {},
    onAttribution: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
    ) {
        Text(
            text = "✨ Settings",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.height(24.dp))
        SettingsEntry(title = "Backup & restore", onClick = onBackup)
        Spacer(Modifier.height(12.dp))
        SettingsEntry(title = "Credits", onClick = onAttribution)
    }
}

@Composable
private fun SettingsEntry(title: String, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .semantics { contentDescription = title },
    ) {
        Text(title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(20.dp))
    }
}

@Preview(showBackground = true)
@Composable
private fun SettingsPreview() {
    AprendeTheme { SettingsScreen() }
}
