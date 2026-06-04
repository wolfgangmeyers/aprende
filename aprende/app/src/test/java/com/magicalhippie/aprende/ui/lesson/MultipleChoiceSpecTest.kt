package com.magicalhippie.aprende.ui.lesson

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class MultipleChoiceSpecTest {

    @Test
    fun `parses valid multiple choice metadata`() {
        val spec = parseMultipleChoiceSpec(
            """{"multipleChoice":{"choices":["we're going home","i have a dog","i want water","i have the water"],"correctIndex":1}}"""
        )

        assertEquals(
            MultipleChoiceSpec(
                choices = listOf("we're going home", "i have a dog", "i want water", "i have the water"),
                correctIndex = 1,
            ),
            spec,
        )
    }

    @Test
    fun `rejects missing duplicate or out of range metadata`() {
        assertNull(parseMultipleChoiceSpec(null))
        assertNull(parseMultipleChoiceSpec("""{"multipleChoice":{"choices":["a","a"],"correctIndex":0}}"""))
        assertNull(parseMultipleChoiceSpec("""{"multipleChoice":{"choices":["a","b"],"correctIndex":2}}"""))
        assertNull(parseMultipleChoiceSpec("""{"choices":["a","b"],"correctIndex":0}"""))
    }
}
