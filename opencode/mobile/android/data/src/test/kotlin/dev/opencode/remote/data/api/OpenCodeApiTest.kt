package dev.opencode.remote.data.api

import dev.opencode.remote.domain.AppSettings
import dev.opencode.remote.domain.ServerProfile
import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Wire-contract tests: paths, Basic auth, bodies (mirror grapeot OpenCodeRepositoryTest). */
class OpenCodeApiTest {

    private lateinit var server: MockWebServer

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
    }

    @After
    fun tearDown() {
        server.close()
    }

    private fun api(user: String = "ucha", pass: String? = "secret") =
        ApiFactory.api(
            ServerProfile(id = "p1", name = "t", baseUrl = server.url("/").toString(), username = user),
            pass,
            AppSettings(),
        )

    @Test
    fun healthParses() = runTest {
        server.enqueue(MockResponse(body = """{"healthy":true,"version":"9.9.9"}"""))
        val h = api().health()
        assertTrue(h.healthy)
        assertEquals("9.9.9", h.version)
        val req = server.takeRequest()
        assertEquals("/global/health", req.target)
        assertEquals("Basic dWNoYTpzZWNyZXQ=", req.headers["Authorization"])
    }

    @Test
    fun promptAsyncPosts204WithAgentAndParts() = runTest {
        server.enqueue(MockResponse(code = 204))
        val res = api().promptAsync(
            "ses_1",
            PromptRequest(parts = listOf(PartInput(type = "text", text = "hi")), agent = "build"),
        )
        assertEquals(204, res.code())
        val req = server.takeRequest()
        assertEquals("/session/ses_1/prompt_async", req.target)
        val body = req.body?.utf8() ?: ""
        assertTrue(body.contains("\"agent\":\"build\""))
        assertTrue(body.contains("\"type\":\"text\""))
    }

    @Test
    fun permissionReplyUsesReplyField() = runTest {
        server.enqueue(MockResponse(body = "true"))
        api().replyPermission("prm_1", PermissionReply(reply = "once"))
        val req = server.takeRequest()
        assertEquals("/permission/prm_1/reply", req.target)
        assertTrue((req.body?.utf8() ?: "").contains("\"reply\":\"once\""))
    }

    @Test
    fun directoryInterceptorAppendsDirectory() = runTest {
        server.enqueue(MockResponse(body = """{"healthy":true,"version":"x"}"""))
        val profile = ServerProfile(
            id = "p1", name = "t", baseUrl = server.url("/").toString(),
            username = "u", defaultDirectory = "/home/u/proj",
        )
        ApiFactory.api(profile, null, AppSettings()).health()
        val req = server.takeRequest()
        assertTrue((req.target ?: "").contains("directory=%2Fhome%2Fu%2Fproj"))
    }
    @Test
    fun questionReplyPostsAnswers() = runTest {
        server.enqueue(MockResponse(body = "true"))
        api().replyQuestion("que_1", dev.opencode.remote.data.api.QuestionReply(listOf(listOf("A"))))
        val req = server.takeRequest()
        assertEquals("/question/que_1/reply", req.target)
        assertTrue((req.body?.utf8() ?: "").contains("\"answers\":[[\"A\"]]"))
    }

    @Test
    fun commandExecutes() = runTest {
        server.enqueue(MockResponse(body = """{"info":{},"parts":[]}"""))
        api().rawCommand("ses_1", dev.opencode.remote.data.api.CommandExecute(command = "init", arguments = "x"))
        val req = server.takeRequest()
        assertEquals("/session/ses_1/command", req.target)
        val body = req.body?.utf8() ?: ""
        assertTrue(body.contains("\"command\":\"init\""))
    }

    @Test
    fun catalogPaths() = runTest {
        server.enqueue(MockResponse(body = """{"all":[]}"""))
        api().rawProviders()
        assertEquals("/provider", server.takeRequest().target)
        server.enqueue(MockResponse(body = "[]"))
        api().rawAgents()
        assertEquals("/agent", server.takeRequest().target)
        server.enqueue(MockResponse(body = "[]"))
        api().rawCommands()
        assertEquals("/command", server.takeRequest().target)
    }
    @Test
    fun promptIncludesSystemModelVariantTools() = runTest {
        server.enqueue(MockResponse(code = 204))
        api().rawPromptAsync(
            "ses_1",
            dev.opencode.remote.data.api.PromptRequest(
                parts = listOf(dev.opencode.remote.data.api.PartInput(type = "text", text = "hi")),
                agent = "plan",
                model = dev.opencode.remote.data.api.ModelInput("meta", "muse-spark-1.3"),
                variant = "high",
                tools = mapOf("webfetch" to false),
                system = "Be brief.",
            ),
        )
        val body = server.takeRequest().body?.utf8() ?: ""
        assertTrue(body.contains("\"system\":\"Be brief.\""))
        assertTrue(body.contains("\"variant\":\"high\""))
        assertTrue(body.contains("\"webfetch\":false"))
        assertTrue(body.contains("\"providerID\":\"meta\""))
    }
}
