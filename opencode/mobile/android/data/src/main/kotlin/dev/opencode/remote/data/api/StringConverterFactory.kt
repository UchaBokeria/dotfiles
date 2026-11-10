package dev.opencode.remote.data.api

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.Converter
import retrofit2.Retrofit
import java.lang.reflect.Type

/** Minimal String converter (avoids the scalars artifact; JSON converter handles the rest). */
object StringConverterFactory : Converter.Factory() {
    override fun responseBodyConverter(
        type: Type,
        annotations: Array<out Annotation>,
        retrofit: Retrofit,
    ): Converter<ResponseBody, *>? =
        if (type == String::class.java) Converter<ResponseBody, String> { it.string() } else null

    override fun requestBodyConverter(
        type: Type,
        parameterAnnotations: Array<out Annotation>,
        methodAnnotations: Array<out Annotation>,
        retrofit: Retrofit,
    ): Converter<*, RequestBody>? =
        if (type == String::class.java) {
            Converter<String, RequestBody> { RequestBody.create("text/plain".toMediaType(), it) }
        } else null
}
