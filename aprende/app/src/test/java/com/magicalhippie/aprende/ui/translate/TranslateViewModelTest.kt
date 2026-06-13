package com.magicalhippie.aprende.ui.translate

import com.magicalhippie.aprende.domain.repository.TranslationRepository
import com.magicalhippie.aprende.domain.translation.TranslationLookupResult
import com.magicalhippie.aprende.domain.translation.TranslationMatch
import com.magicalhippie.aprende.domain.translation.TranslationMatchKind
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class TranslateViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `lookup publishes trimmed offline result`() = runTest(dispatcher) {
        val repo = FakeTranslationRepository(
            result = TranslationLookupResult(
                query = "perro",
                matches = listOf(TranslationMatch("perro", "dog", TranslationMatchKind.WORD)),
            ),
        )
        val viewModel = TranslateViewModel(repo)

        viewModel.onQueryChange("  perro  ")
        viewModel.lookup()
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals("perro", repo.lastInput)
        assertFalse(state.loading)
        assertEquals("dog", state.result?.bestEnglish)
        assertNull(state.message)
    }

    @Test
    fun `blank lookup asks for input without calling repository`() = runTest(dispatcher) {
        val repo = FakeTranslationRepository()
        val viewModel = TranslateViewModel(repo)

        viewModel.lookup()

        val state = viewModel.uiState.value
        assertEquals(null, repo.lastInput)
        assertEquals("Enter a Spanish word or phrase.", state.message)
        assertNull(state.result)
    }

    @Test
    fun `empty repository result shows no local match message`() = runTest(dispatcher) {
        val viewModel = TranslateViewModel(FakeTranslationRepository())

        viewModel.onQueryChange("desconocido")
        viewModel.lookup()
        advanceUntilIdle()

        assertEquals("No local match found.", viewModel.uiState.value.message)
    }

    @Test
    fun `query edit clears previous result`() = runTest(dispatcher) {
        val viewModel = TranslateViewModel(
            FakeTranslationRepository(
                result = TranslationLookupResult(
                    query = "perro",
                    matches = listOf(TranslationMatch("perro", "dog", TranslationMatchKind.WORD)),
                ),
            ),
        )

        viewModel.onQueryChange("perro")
        viewModel.lookup()
        advanceUntilIdle()

        viewModel.onQueryChange("gato")

        assertNull(viewModel.uiState.value.result)
        assertNull(viewModel.uiState.value.message)
        assertFalse(viewModel.uiState.value.loading)
    }

    @Test
    fun `new lookup cannot be overwritten by slower old lookup`() = runTest(dispatcher) {
        val viewModel = TranslateViewModel(
            FakeTranslationRepository(
                results = mapOf(
                    "perro" to TranslationLookupResult(
                        query = "perro",
                        matches = listOf(TranslationMatch("perro", "dog", TranslationMatchKind.WORD)),
                    ),
                    "gato" to TranslationLookupResult(
                        query = "gato",
                        matches = listOf(TranslationMatch("gato", "cat", TranslationMatchKind.WORD)),
                    ),
                ),
                delays = mapOf("perro" to 1_000L),
            ),
        )

        viewModel.onQueryChange("perro")
        viewModel.lookup()
        viewModel.onQueryChange("gato")
        viewModel.lookup()
        advanceUntilIdle()

        assertEquals("cat", viewModel.uiState.value.result?.bestEnglish)
    }
}

private class FakeTranslationRepository(
    private val result: TranslationLookupResult = TranslationLookupResult("", emptyList()),
    private val results: Map<String, TranslationLookupResult> = emptyMap(),
    private val delays: Map<String, Long> = emptyMap(),
) : TranslationRepository {
    var lastInput: String? = null

    override suspend fun lookupSpanishToEnglish(input: String): TranslationLookupResult {
        lastInput = input
        delays[input]?.let { delay(it) }
        return results[input] ?: if (result.query.isBlank()) result.copy(query = input) else result
    }
}
