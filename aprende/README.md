# Aprende

Client-only, fully-offline Spanish learning app for Android (P0.1 scaffold).

This is the buildable skeleton from **PLAN.md → P0.1**: the layered architecture,
the Hilt DI graph, a trivial Home screen + ViewModel, and the JVM test harness that
CI runs. No business logic yet — FSRS (P0.2), the content pipeline (P0.3), and the
MVP loop (P1.x) build on this.

## Stack

Source of truth: `SPEC.md` §3, §12, §13.

- **Language/UI:** Kotlin + Jetpack Compose (Material 3)
- **DI:** Hilt
- **Persistence:** Room (two DBs — read-only `content.db`, read-write `progress.db`)
  + Jetpack DataStore (settings)
- **Async:** Kotlin coroutines / Flow
- **Navigation:** Navigation Compose
- **Build:** Gradle **Kotlin DSL** + a **version catalog** (`gradle/libs.versions.toml`
  is the single source of all versions)
- **SDK:** `compileSdk = 35`, `minSdk = 24`, `targetSdk = 35`; Java/JVM target **17**

### Pinned versions (see `gradle/libs.versions.toml`)

| Component | Version |
|---|---|
| Android Gradle Plugin | 8.7.3 |
| Gradle (wrapper) | 8.11.1 |
| Kotlin | 2.1.0 |
| KSP | 2.1.0-1.0.29 |
| Compose compiler plugin (`org.jetbrains.kotlin.plugin.compose`) | versioned with Kotlin (2.1.0) |
| Compose BOM | 2024.12.01 |
| Hilt | 2.52 |
| Room | 2.6.1 |
| DataStore | 1.1.1 |
| Lifecycle | 2.8.7 |
| Navigation Compose | 2.8.5 |
| Coroutines | 1.9.0 |
| Robolectric | 4.14.1 |
| Turbine | 1.1.0 |

The tightly-coupled quartet is **Kotlin ↔ KSP ↔ Compose compiler plugin ↔ Compose
BOM** (with AGP alongside). Bump them together.

## Module / package layout

Single Gradle module `:app`. Packages mirror SPEC §12.1 layers
(`ui → domain → data`, with `di` for Hilt modules):

```
app/src/main/java/com/magicalhippie/aprende/
  ui/      Compose screens + ViewModels (UiState as StateFlow)
    theme/ Material 3 theme
    home/  smoke-test screen + ViewModel
  domain/  pure-Kotlin use-cases / rules — NO Android/Room imports (JVM-testable)
  data/    Room DAOs, DataStore, repository impls — the only layer that knows persistence
  di/      Hilt modules (provides java.time.Clock, §12.3)
```

`domain/` and `data/` currently hold marker files only; they exist so the layers and
dependency direction are visible from iteration one.

## Build & test

Requires **JDK 17** and the Android SDK (`compileSdk 35` / build-tools).

```bash
./gradlew testDebugUnitTest   # JVM unit tests (Turbine StateFlow + Robolectric Compose)
./gradlew assembleDebug       # build the debug APK
./gradlew connectedDebugAndroidTest   # instrumented tests (needs a device/emulator)
```

## ⚠️ Content DB asset is generated, not committed

The read-only `content.db` Room asset (and `content_manifest.json`) are reproducible
outputs of the content pipeline and are **gitignored** — like the gradle wrapper jar,
regenerate them once before assembling the app (Room's `createFromAsset` validates the
bundled asset against the exported schema and fails the build if it's missing/mismatched):

```bash
cd aprende
python3 tools/content-pipeline/build_content_db.py --out app/src/main/assets/database/content.db
```

See `tools/content-pipeline/README.md` for the vetting workflow and the AC17 publish gate.

## ⚠️ Gradle wrapper jar is not committed

`gradle/wrapper/gradle-wrapper.jar` (a binary) is intentionally **absent** from this
scaffold. Before the first build or CI run, materialize it once in a JDK/Gradle
environment:

```bash
cd aprende
gradle wrapper --gradle-version 8.11.1
```

That generates the jar (and `gradlew` / `gradlew.bat`) to match
`gradle/wrapper/gradle-wrapper.properties`. Commit them for local use, then
`./gradlew ...` works. **CI does this automatically** (see below), so committing the
wrapper is optional but recommended for local dev.

## CI

`.github/workflows/android-ci.yml` runs three jobs on push/PR:
- **unit-tests** — JDK 17 → `gradle/actions/setup-gradle` → **`gradle wrapper --gradle-version 8.11.1`** (materializes `gradlew` + the jar since they aren't committed) → `./gradlew testDebugUnitTest` (Robolectric + Turbine JVM tests).
- **content-vetting-gate** — runs the content pipeline and asserts the publish gate **rejects** an injected unvetted row (enforces C5/§4.6/**AC17** in CI).
- **instrumented-tests** — generates `content.db`, boots an emulator (`reactivecircus/android-emulator-runner`), and runs `connectedDebugAndroidTest` (the **AC1** airplane-mode E2E + **AC12** process-death).
