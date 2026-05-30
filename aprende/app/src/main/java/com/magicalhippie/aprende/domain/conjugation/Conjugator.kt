package com.magicalhippie.aprende.domain.conjugation

/** The six persons a verb conjugates for. */
enum class Person { YO, TU, EL, NOSOTROS, VOSOTROS, ELLOS }

/**
 * Tenses an A1–B1 course teaches and that the regular generator covers (SPEC §5.2).
 * Imperative is intentionally excluded from the regular generator (it is largely derived /
 * irregular — affirmative tú = 3rd-sing present, negative = subjunctive, plus 8 irregulars)
 * and is sourced as vetted content where needed.
 */
enum class Tense { PRESENT, PRETERITE, IMPERFECT, FUTURE, PRESENT_SUBJUNCTIVE }

/** -ar / -er / -ir, derived from the infinitive ending. */
enum class VerbClass { AR, ER, IR }

/**
 * Source of irregular/stem-changing conjugation forms. Per C5/§4.6, irregular forms are
 * **vetted content** (sourced e.g. from Wiktionary, reviewed, shipped in content.db) — NOT
 * hardcoded here, because a wrong conjugation actively mis-teaches. Returns null when the
 * form is regular (the [Conjugator] then applies the deterministic rule).
 */
interface IrregularFormSource {
    fun override(lemma: String, tense: Tense, person: Person): String?
}

/** An [IrregularFormSource] with no overrides — every verb conjugates regularly. */
object NoIrregularForms : IrregularFormSource {
    override fun override(lemma: String, tense: Tense, person: Person): String? = null
}

/**
 * Generates Spanish verb forms (SPEC §5.2). The **regular** endings are a deterministic
 * algorithm (language structure, not invented per-word data) verified against authoritative
 * grammar references. **Irregular** forms come from an injected [IrregularFormSource] (vetted
 * content). So: look up an override; if none, apply the regular rule for the verb's class.
 */
class Conjugator(private val irregular: IrregularFormSource = NoIrregularForms) {

    fun verbClassOf(infinitive: String): VerbClass = when {
        infinitive.endsWith("ar") -> VerbClass.AR
        infinitive.endsWith("er") -> VerbClass.ER
        infinitive.endsWith("ir") -> VerbClass.IR
        else -> throw IllegalArgumentException("Not a conjugatable infinitive: $infinitive")
    }

    fun conjugate(infinitive: String, tense: Tense, person: Person): String {
        irregular.override(infinitive, tense, person)?.let { return it }
        val verbClass = verbClassOf(infinitive)
        val ending = endingFor(verbClass, tense, person)
        // Future endings attach to the full infinitive; all other tenses use the stem.
        return if (tense == Tense.FUTURE) infinitive + ending else stemOf(infinitive) + ending
    }

    /** Full regular paradigm (6 persons) for a tense — convenience for tests/exercise generation. */
    fun paradigm(infinitive: String, tense: Tense): Map<Person, String> =
        Person.entries.associateWith { conjugate(infinitive, tense, it) }

    private fun stemOf(infinitive: String): String = infinitive.dropLast(2)

    private fun endingFor(verbClass: VerbClass, tense: Tense, person: Person): String {
        val endings = ENDINGS[tense]!![verbClass]!!
        return endings[person.ordinal]
    }

    companion object {
        // Regular endings, person order: YO, TU, EL, NOSOTROS, VOSOTROS, ELLOS (SPEC §5.2, verified).
        // FUTURE endings are identical across classes and attach to the whole infinitive.
        private val FUTURE = listOf("é", "ás", "á", "emos", "éis", "án")

        private val ENDINGS: Map<Tense, Map<VerbClass, List<String>>> = mapOf(
            Tense.PRESENT to mapOf(
                VerbClass.AR to listOf("o", "as", "a", "amos", "áis", "an"),
                VerbClass.ER to listOf("o", "es", "e", "emos", "éis", "en"),
                VerbClass.IR to listOf("o", "es", "e", "imos", "ís", "en"),
            ),
            Tense.PRETERITE to mapOf(
                VerbClass.AR to listOf("é", "aste", "ó", "amos", "asteis", "aron"),
                VerbClass.ER to listOf("í", "iste", "ió", "imos", "isteis", "ieron"),
                VerbClass.IR to listOf("í", "iste", "ió", "imos", "isteis", "ieron"),
            ),
            Tense.IMPERFECT to mapOf(
                VerbClass.AR to listOf("aba", "abas", "aba", "ábamos", "abais", "aban"),
                VerbClass.ER to listOf("ía", "ías", "ía", "íamos", "íais", "ían"),
                VerbClass.IR to listOf("ía", "ías", "ía", "íamos", "íais", "ían"),
            ),
            Tense.FUTURE to mapOf(
                VerbClass.AR to FUTURE,
                VerbClass.ER to FUTURE,
                VerbClass.IR to FUTURE,
            ),
            Tense.PRESENT_SUBJUNCTIVE to mapOf(
                VerbClass.AR to listOf("e", "es", "e", "emos", "éis", "en"),
                VerbClass.ER to listOf("a", "as", "a", "amos", "áis", "an"),
                VerbClass.IR to listOf("a", "as", "a", "amos", "áis", "an"),
            ),
        )
    }
}
