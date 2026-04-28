package com.elite.iptv.dvr.api

import com.google.gson.JsonDeserializationContext
import com.google.gson.JsonDeserializer
import com.google.gson.JsonElement
import java.lang.reflect.Type

/**
 * Xtream / JSON often sends EPG start|stop as numbers; Gson would otherwise fail
 * mapping into [String] fields on [EpgListing].
 */
internal object EpgListingDeserializer : JsonDeserializer<EpgListing> {
    override fun deserialize(json: JsonElement, typeOfT: Type, context: JsonDeserializationContext): EpgListing {
        val o = json.asJsonObject
        fun flexString(name: String): String? {
            if (!o.has(name)) return null
            val e = o.get(name) ?: return null
            if (e.isJsonNull) return null
            val p = e.asJsonPrimitive
            return when {
                p.isString -> p.asString
                p.isNumber -> p.asNumber.toString()
                else -> null
            }
        }
        val title = o.get("title")?.takeIf { !it.isJsonNull }?.asString ?: ""
        val desc = o.get("description")?.takeIf { !it.isJsonNull }?.asString
        val start = flexString("start")
        val stop = flexString("stop") ?: flexString("end")
        return EpgListing(title = title, description = desc, start = start, stop = stop)
    }
}
