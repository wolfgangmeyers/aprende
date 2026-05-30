package com.magicalhippie.aprende.domain.conjugation

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Regular conjugation generation (SPEC §5.2) and irregular-override application (AC4).
 * Expected forms verified against an independent reference. Person order:
 * YO, TU, EL, NOSOTROS, VOSOTROS, ELLOS.
 */
class ConjugatorTest {

    private val conjugator = Conjugator()

    private fun forms(infinitive: String, tense: Tense): List<String> =
        Person.entries.map { conjugator.conjugate(infinitive, tense, it) }

    @Test
    fun `regular -ar present`() {
        assertEquals(listOf("hablo", "hablas", "habla", "hablamos", "habláis", "hablan"), forms("hablar", Tense.PRESENT))
    }

    @Test
    fun `regular -er present`() {
        assertEquals(listOf("como", "comes", "come", "comemos", "coméis", "comen"), forms("comer", Tense.PRESENT))
    }

    @Test
    fun `regular -ir present`() {
        assertEquals(listOf("vivo", "vives", "vive", "vivimos", "vivís", "viven"), forms("vivir", Tense.PRESENT))
    }

    @Test
    fun `regular preterite`() {
        assertEquals(listOf("hablé", "hablaste", "habló", "hablamos", "hablasteis", "hablaron"), forms("hablar", Tense.PRETERITE))
        assertEquals(listOf("comí", "comiste", "comió", "comimos", "comisteis", "comieron"), forms("comer", Tense.PRETERITE))
    }

    @Test
    fun `regular imperfect`() {
        assertEquals(listOf("vivía", "vivías", "vivía", "vivíamos", "vivíais", "vivían"), forms("vivir", Tense.IMPERFECT))
    }

    @Test
    fun `regular future attaches endings to the whole infinitive`() {
        assertEquals(listOf("hablaré", "hablarás", "hablará", "hablaremos", "hablaréis", "hablarán"), forms("hablar", Tense.FUTURE))
    }

    @Test
    fun `regular present subjunctive uses the opposite vowel`() {
        assertEquals(listOf("coma", "comas", "coma", "comamos", "comáis", "coman"), forms("comer", Tense.PRESENT_SUBJUNCTIVE))
        assertEquals(listOf("viva", "vivas", "viva", "vivamos", "viváis", "vivan"), forms("vivir", Tense.PRESENT_SUBJUNCTIVE))
    }

    @Test
    fun `non-infinitive input is rejected`() {
        try {
            conjugator.conjugate("perro", Tense.PRESENT, Person.YO)
            throw AssertionError("expected IllegalArgumentException")
        } catch (e: IllegalArgumentException) {
            // expected
        }
    }

    @Test
    fun `AC4 - irregular forms come from the override source, not the regular rule`() {
        // The override source stands in for VETTED CONTENT (C5): irregular forms are sourced
        // and reviewed, never hardcoded. Here a fake supplies a few ser/estar/tener forms.
        val irregulars = mapOf(
            Triple("ser", Tense.PRESENT, Person.YO) to "soy",
            Triple("ser", Tense.PRESENT, Person.TU) to "eres",
            Triple("ser", Tense.PRESENT, Person.EL) to "es",
            Triple("estar", Tense.PRESENT, Person.YO) to "estoy",
            Triple("tener", Tense.PRESENT, Person.YO) to "tengo",
        )
        val source = object : IrregularFormSource {
            override fun override(lemma: String, tense: Tense, person: Person): String? =
                irregulars[Triple(lemma, tense, person)]
        }
        val c = Conjugator(source)

        assertEquals("soy", c.conjugate("ser", Tense.PRESENT, Person.YO))
        assertEquals("eres", c.conjugate("ser", Tense.PRESENT, Person.TU))
        assertEquals("estoy", c.conjugate("estar", Tense.PRESENT, Person.YO))
        assertEquals("tengo", c.conjugate("tener", Tense.PRESENT, Person.YO))

        // No override for tener/nosotros/present here -> falls back to the regular rule.
        assertEquals("tenemos", c.conjugate("tener", Tense.PRESENT, Person.NOSOTROS))
    }
}
