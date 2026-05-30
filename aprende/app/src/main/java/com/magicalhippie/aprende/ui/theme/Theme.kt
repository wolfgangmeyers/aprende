package com.magicalhippie.aprende.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val DarkColorScheme = darkColorScheme(
    primary = MagicPurple80,
    secondary = MagicPurpleGrey80,
    tertiary = Gold80,
)

private val LightColorScheme = lightColorScheme(
    primary = MagicPurple40,
    secondary = MagicPurpleGrey40,
    tertiary = Gold40,
)

/**
 * App-wide Material 3 theme.
 *
 * @param dynamicColor when true (and on Android 12+), derives the scheme from the
 *   device wallpaper (Material You). Defaults to off so the brand palette is stable
 *   across devices; callers can opt in.
 */
@Composable
fun AprendeTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }

        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content,
    )
}
