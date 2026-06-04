package com.magicalhippie.aprende.ui.lesson

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

data class MultipleChoiceSpec(
    val choices: List<String>,
    val correctIndex: Int,
)

fun parseMultipleChoiceSpec(promptHint: String?): MultipleChoiceSpec? {
    if (promptHint.isNullOrBlank()) return null
    return runCatching {
        val root = Json.parseToJsonElement(promptHint).jsonObject
        val spec = root["multipleChoice"] as? JsonObject ?: return@runCatching null
        val choices = (spec["choices"] as? JsonArray)
            ?.map { it.jsonPrimitive.content.trim() }
            ?.filter { it.isNotEmpty() }
            ?: return@runCatching null
        val correctIndex = spec["correctIndex"]?.jsonPrimitive?.intOrNull ?: return@runCatching null
        if (
            choices.size < 2 ||
            choices.distinct().size != choices.size ||
            correctIndex !in choices.indices
        ) {
            null
        } else {
            MultipleChoiceSpec(choices = choices, correctIndex = correctIndex)
        }
    }.getOrNull()
}
