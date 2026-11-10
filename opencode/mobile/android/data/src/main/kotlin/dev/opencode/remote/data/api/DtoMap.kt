package dev.opencode.remote.data.api

import dev.opencode.remote.domain.ChatMessage
import dev.opencode.remote.domain.ChatPart
import dev.opencode.remote.domain.ChatSession
import dev.opencode.remote.domain.Role
import dev.opencode.remote.domain.SessionStatus
import dev.opencode.remote.domain.SseEvent
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull

private val json = Json { ignoreUnknownKeys = true; isLenient = true; coerceInputValues = true }

/** Lenient mappers: server DTOs → domain (unknown shapes degrade, never crash). */
object DtoMap {

    fun session(o: JsonObject): ChatSession = ChatSession(
        id = o.getString("id"),
        title = o.getString("title"),
        directory = o.getString("directory"),
        projectID = o.getString("projectID"),
        parentID = o.getStringOrNull("parentID"),
        updatedAt = o.getObjectOrNull("time")?.getLong("updated") ?: 0,
    )

    fun status(o: JsonObject): SessionStatus = SessionStatus(
        type = o.getString("type", "idle"),
        attempt = 0,
        message = o.getStringOrNull("message"),
    )

    fun message(o: JsonObject, parts: List<JsonObject>): ChatMessage {
        val info = o.getObjectOrNull("info") ?: o
        val role = when (info.getStringOrNull("role")) {
            "user" -> Role.USER
            "assistant" -> Role.ASSISTANT
            else -> Role.UNKNOWN
        }
        val errObj = info.getObjectOrNull("error")
        val err = errObj?.let {
            it.getStringOrNull("message")
                ?: it.getObjectOrNull("data")?.getStringOrNull("message")
                ?: it.getStringOrNull("name")
        } ?: info.getStringOrNull("error")
        val list = (o.getArrayOrNull("parts") ?: parts).mapNotNull { el ->
            (el as? JsonObject)?.let(::part)
        }
        return ChatMessage(
            id = info.getString("id"),
            role = role,
            parts = list,
            error = err,
        )
    }

    fun part(o: JsonObject): ChatPart = when (o.getString("type")) {
        "text" -> ChatPart.Text(o.getString("text"))
        "reasoning" -> ChatPart.Reasoning(o.getString("text"))
        "tool" -> ChatPart.Tool(
            callID = o.getStringOrNull("callID") ?: "",
            tool = o.getStringOrNull("tool") ?: "",
            state = o.getString("state", "pending"),
        )
        "step-start" -> ChatPart.StepStart(o.getStringOrNull("id") ?: "")
        "step-finish" -> {
            val tokens = o.getObjectOrNull("tokens")
            ChatPart.StepFinish(
                cost = o.getDouble("cost"),
                input = tokens?.getLong("input") ?: 0,
                output = tokens?.getLong("output") ?: 0,
            )
        }
        "file" -> ChatPart.File(o.getString("mime", ""), o.getString("filename", ""), o.getString("url", ""))
        "patch" -> ChatPart.Patch(o.getArrayOrNull("files")?.size ?: 0)
        "agent" -> ChatPart.Agent(o.getString("name", ""))
        "retry" -> ChatPart.Retry(o.getInt("attempt"), o.getString("error", ""))
        "compaction" -> ChatPart.Compaction(o.getString("text", ""))
        "subtask" -> ChatPart.Subtask(o.getString("prompt", ""))
        else -> ChatPart.Unknown(o.getString("type"))
    }

    /**
     * Raw SSE frame → SseEvent. Returns null for heartbeat/noise (caller skips).
     * Wire shapes (verified live 2026-10-04):
     * - v1 `/event`: `{"id","type","sessionID",...}` (fields top-level)
     * - `/global/event`: `{"directory","project","payload":{"id","type","properties":{...}}}}`
     *   (GlobalEvent wrapper; IDs live inside `properties`)
     */
    fun event(type: String?, data: String): SseEvent? {
        if (type == "open") return null
        val root = runCatching { json.parseToJsonElement(data).jsonObject }.getOrNull() ?: return null
        val o = if (root.getStringOrNull("type") == null) {
            root.getObjectOrNull("payload") ?: root
        } else {
            root
        }
        val t = o.getStringOrNull("type") ?: type ?: return null
        if (t == "server.heartbeat" || t == "server.connected") return null
        val props = o.getObjectOrNull("properties")
        fun id(vararg keys: String): String? =
            keys.firstNotNullOfOrNull { o.getStringOrNull(it) }
                ?: keys.firstNotNullOfOrNull { props?.getStringOrNull(it) }
        val errObj = o.getObjectOrNull("error") ?: props?.getObjectOrNull("error")
        val errMsg = errObj?.let {
            it.getObjectOrNull("data")?.getStringOrNull("message")
                ?: it.getStringOrNull("message")
                ?: it.getStringOrNull("name")
        }
        return SseEvent(
            type = t,
            sessionID = id("sessionID", "sessionId"),
            messageID = id("messageID", "messageId"),
            partID = id("partID", "partId")
                ?: o.getObjectOrNull("part")?.getStringOrNull("id")
                ?: props?.getObjectOrNull("part")?.getStringOrNull("id"),
            delta = o.getStringOrNull("delta") ?: props?.getStringOrNull("delta"),
            errorMessage = errMsg,
            requestID = id("requestID", "requestId"),
            raw = data,
        )
    }

    // --- small accessors (non-primitive values yield defaults, never throw) ---
    private fun JsonObject.prim(key: String): kotlinx.serialization.json.JsonPrimitive? =
        get(key) as? kotlinx.serialization.json.JsonPrimitive

    private fun JsonObject.getString(key: String, default: String = ""): String =
        prim(key)?.contentOrNull ?: default

    private fun JsonObject.getStringOrNull(key: String): String? =
        prim(key)?.contentOrNull

    private fun JsonObject.getLong(key: String): Long =
        prim(key)?.longOrNull ?: 0

    private fun JsonObject.getDouble(key: String): Double =
        prim(key)?.doubleOrNull ?: 0.0

    private fun JsonObject.getInt(key: String): Int =
        prim(key)?.contentOrNull?.toIntOrNull() ?: 0

    private fun JsonObject.getObjectOrNull(key: String): JsonObject? =
        get(key) as? JsonObject

    private fun JsonObject.getArrayOrNull(key: String) =
        (get(key) as? kotlinx.serialization.json.JsonArray)?.toList()

    fun parseSessions(body: String): List<ChatSession> =
        runCatching {
            json.parseToJsonElement(body).jsonArray.mapNotNull {
                (it as? JsonObject)?.let(::session)
            }
        }.getOrElse { emptyList() }

    fun parseStatusMap(body: String): Map<String, SessionStatus> =
        runCatching {
            json.parseToJsonElement(body).jsonObject.mapValues { (_, v) ->
                (v as? JsonObject)?.let(::status) ?: SessionStatus()
            }
        }.getOrElse { emptyMap() }

    fun parseMessages(body: String): List<ChatMessage> =
        runCatching {
            json.parseToJsonElement(body).jsonArray.mapNotNull {
                (it as? JsonObject)?.let { o -> message(o, emptyList()) }
            }
        }.getOrElse { emptyList() }

    fun parseHealth(body: String): Pair<Boolean, String> =
        runCatching {
            val o = json.parseToJsonElement(body).jsonObject
            ((o["healthy"] as? kotlinx.serialization.json.JsonPrimitive)?.booleanOrNull ?: false) to
                ((o["version"] as? kotlinx.serialization.json.JsonPrimitive)?.contentOrNull ?: "")
        }.getOrElse { false to "" }

    // --- P2: approvals / catalog ---
    fun parsePermissions(body: String): List<dev.opencode.remote.domain.PermissionItem> =
        runCatching {
            json.parseToJsonElement(body).jsonArray.mapNotNull { el ->
                (el as? JsonObject)?.let { o ->
                    val tool = o.getObjectOrNull("tool")
                    dev.opencode.remote.domain.PermissionItem(
                        id = o.getString("id"),
                        sessionID = o.getString("sessionID"),
                        permission = o.getString("permission"),
                        patterns = o.getArrayOrNull("patterns")?.mapNotNull {
                            (it as? kotlinx.serialization.json.JsonPrimitive)?.contentOrNull
                        } ?: emptyList(),
                        always = o.getArrayOrNull("always")?.mapNotNull {
                            (it as? kotlinx.serialization.json.JsonPrimitive)?.contentOrNull
                        } ?: emptyList(),
                        messageID = tool?.getStringOrNull("messageID"),
                        callID = tool?.getStringOrNull("callID"),
                    )
                }
            }
        }.getOrElse { emptyList() }

    fun parseQuestions(body: String): List<dev.opencode.remote.domain.QuestionItem> =
        runCatching {
            json.parseToJsonElement(body).jsonArray.mapNotNull { el ->
                val o = el as? JsonObject ?: return@mapNotNull null
                val prompts = o.getArrayOrNull("questions")?.mapNotNull { q ->
                    (q as? JsonObject)?.let { qi ->
                        dev.opencode.remote.domain.QuestionPrompt(
                            header = qi.getString("header"),
                            question = qi.getString("question"),
                            options = qi.getArrayOrNull("options")?.mapNotNull { op ->
                                (op as? JsonObject)?.let {
                                    dev.opencode.remote.domain.QuestionOption(
                                        it.getString("label"),
                                        it.getString("description"),
                                    )
                                }
                            } ?: emptyList(),
                            multiple = qi.prim("multiple")?.let {
                                it.booleanOrNull ?: (it.contentOrNull == "true")
                            } ?: false,
                            customAllowed = qi.prim("custom")?.let {
                                it.booleanOrNull ?: (it.contentOrNull == "true")
                            } ?: false,
                        )
                    }
                } ?: emptyList()
                if (prompts.isEmpty()) return@mapNotNull null
                dev.opencode.remote.domain.QuestionItem(
                    id = o.getString("id"),
                    sessionID = o.getString("sessionID"),
                    questions = prompts,
                )
            }
        }.getOrElse { emptyList() }

    fun parseProviders(body: String): List<dev.opencode.remote.domain.ProviderInfo> =
        runCatching {
            val root = json.parseToJsonElement(body).jsonObject
            // GET /provider returns {all:[...],...}; be lenient to bare arrays too.
            val arr = root.getArrayOrNull("all")
                ?: root.getArrayOrNull("providers")
                ?: return@runCatching emptyList<dev.opencode.remote.domain.ProviderInfo>()
            arr.mapNotNull { el ->
                (el as? JsonObject)?.let { o ->
                    val models = o.getObjectOrNull("models")?.entries?.map { (mid, mv) ->
                        val mo = mv as? JsonObject
                        dev.opencode.remote.domain.ModelInfo(
                            id = mid,
                            name = mo?.getStringOrNull("name") ?: mid,
                            contextLimit = mo?.getObjectOrNull("limit")?.getLong("context") ?: 0,
                        )
                    } ?: emptyList()
                    dev.opencode.remote.domain.ProviderInfo(
                        id = o.getString("id"),
                        name = o.getStringOrNull("name") ?: o.getString("id"),
                        models = models,
                    )
                }
            }
        }.getOrElse { emptyList() }

    fun parseAgents(body: String): List<dev.opencode.remote.domain.AgentInfo> =
        runCatching {
            json.parseToJsonElement(body).jsonArray.mapNotNull { el ->
                (el as? JsonObject)?.let { o ->
                    val hidden = o.prim("hidden")?.let {
                        it.booleanOrNull ?: (it.contentOrNull == "true")
                    } ?: false
                    if (hidden) return@mapNotNull null
                    dev.opencode.remote.domain.AgentInfo(
                        name = o.getString("name"),
                        description = o.getString("description"),
                        mode = o.getString("mode", "all"),
                    )
                }
            }
        }.getOrElse { emptyList() }

    fun parseCommands(body: String): List<dev.opencode.remote.domain.CommandInfo> =
        runCatching {
            json.parseToJsonElement(body).jsonArray.mapNotNull { el ->
                (el as? JsonObject)?.let { o ->
                    dev.opencode.remote.domain.CommandInfo(
                        name = o.getString("name"),
                        description = o.getString("description"),
                        source = o.getString("source"),
                    )
                }
            }
        }.getOrElse { emptyList() }

    fun parseMcp(body: String): List<dev.opencode.remote.domain.McpServerInfo> =
        runCatching {
            json.parseToJsonElement(body).jsonObject.entries.map { (name, v) ->
                val o = v as? JsonObject
                dev.opencode.remote.domain.McpServerInfo(
                    name = name,
                    status = o?.getStringOrNull("status")
                        ?: o?.getStringOrNull("state")
                        ?: (if (v.toString() == "true") "connected" else v.toString().take(40)),
                )
            }
        }.getOrElse { emptyList() }

    fun parseToolIds(body: String): List<String> =
        runCatching {
            json.parseToJsonElement(body).jsonArray.mapNotNull {
                (it as? kotlinx.serialization.json.JsonPrimitive)?.contentOrNull
            }
        }.getOrElse { emptyList() }
}
