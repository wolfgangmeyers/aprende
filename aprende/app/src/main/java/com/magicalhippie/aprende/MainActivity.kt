package com.magicalhippie.aprende

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.magicalhippie.aprende.ui.navigation.AprendeNavHost
import com.magicalhippie.aprende.ui.theme.AprendeTheme
import dagger.hilt.android.AndroidEntryPoint

/**
 * Single-activity host. [AndroidEntryPoint] lets Hilt inject into Compose-hosted
 * ViewModels (via [androidx.hilt.navigation.compose.hiltViewModel]). All real UI
 * lives in Compose under [AprendeTheme], driven by [AprendeNavHost] (SPEC §12.2).
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            AprendeTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    AprendeNavHost()
                }
            }
        }
    }
}
