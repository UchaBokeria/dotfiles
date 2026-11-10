package dev.opencode.remote.data.api

import dev.opencode.remote.domain.ChatPart
import dev.opencode.remote.domain.Role
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** DtoMap: lenient parsing, unknown shapes degrade, heartbeats skipped. */
class DtoMapTest {

    @Test
    fun parsesSessionList() {
        val body = """[{"id":"ses_1","title":"hello","directory":"/tmp","projectID":"p",
          "time":{"created":1,"updated":2}}]"""
        val list = DtoMap.parseSessions(body)
        assertEquals(1, list.size)
        assertEquals("ses_1", list[0].id)
        assertEquals("hello", list[0].title)
        assertEquals(2, list[0].updatedAt)
    }

    @Test
    fun parsesMessagesWithParts() {
        val body = """[{"info":{"id":"m1","role":"user"},
          "parts":[{"id":"p1","type":"text","text":"hi"}]},
          {"info":{"id":"m2","role":"assistant"},
          "parts":[{"id":"p2","type":"text","text":"hello"},
            {"id":"p3","type":"tool","tool":"bash","state":"completed","callID":"c1"},
            {"id":"p4","type":"mystery-future","x":1}]}]"""
        val msgs = DtoMap.parseMessages(body)
        assertEquals(2, msgs.size)
        assertEquals(Role.USER, msgs[0].role)
        assertTrue(msgs[0].parts[0] is ChatPart.Text)
        assertTrue(msgs[1].parts[1] is ChatPart.Tool)
        assertTrue(msgs[1].parts[2] is ChatPart.Unknown)
    }

    @Test
    fun heartbeatAndConnectedSkipped() {
        assertNull(DtoMap.event("message", """{"type":"server.heartbeat"}"""))
        assertNull(DtoMap.event("message", """{"type":"server.connected","properties":{}}"""))
        assertNull(DtoMap.event("open", ""))
    }

    @Test
    fun deltaEventExtractsIds() {
        val ev = DtoMap.event(
            "message",
            """{"type":"message.part.delta","sessionID":"ses_1","messageID":"m9",
              "partID":"prt_1","delta":"hel"}""",
        )!!
        assertEquals("message.part.delta", ev.type)
        assertEquals("ses_1", ev.sessionID)
        assertEquals("m9", ev.messageID)
        assertEquals("prt_1", ev.partID)
        assertEquals("hel", ev.delta)
    }

    @Test
    fun globalEventWrapperUnwrapped() {
        // Live /global/event shape: IDs nested in properties (verified 2026-10-04).
        val ev = DtoMap.event(
            null,
            """{"directory":"/home/u","project":"global","payload":{"id":"evt_1","type":"session.idle","properties":{"sessionID":"ses_9"}}}""",
        )!!
        assertEquals("session.idle", ev.type)
        assertEquals("ses_9", ev.sessionID)
        assertNull(
            DtoMap.event(
                null,
                """{"payload":{"id":"evt_2","type":"server.connected","properties":{}}}""",
            ),
        )
    }

    @Test
    fun sessionErrorExtractsMessage() {
        val ev = DtoMap.event(
            null,
            """{"directory":"/home/u","payload":{"id":"evt_3","type":"session.error","properties":{"sessionID":"ses_1","error":{"name":"APIError","data":{"message":"Billing verification failed."}}}}}""",
        )!!
        assertEquals("session.error", ev.type)
        assertEquals("ses_1", ev.sessionID)
        assertEquals("Billing verification failed.", ev.errorMessage)
    }

    @Test
    fun garbageNeverCrashes() {
        assertEquals(0, DtoMap.parseSessions("not json").size)
        assertEquals(0, DtoMap.parseMessages("[{broken").size)
        assertEquals(0, DtoMap.parseStatusMap("null").size)
        assertNull(DtoMap.event("message", "garbage"))
    }

    @Test
    fun parsesReal584kPayload() {
        val body = DtoMapTest::class.java.getResource("/real-msgs.json")!!.readText()
        val msgs = DtoMap.parseMessages(body)
        assertEquals(24, msgs.size)
    }
    @Test
    fun parsesPermissions() {
        val body = """[{"id":"per_1","sessionID":"ses_1","permission":"bash","patterns":["rm *"],
          "metadata":{"filepath":"/tmp"},"always":[],"tool":{"messageID":"m1","callID":"c1"}}]"""
        val list = DtoMap.parsePermissions(body)
        assertEquals(1, list.size)
        assertEquals("bash", list[0].permission)
        assertEquals(listOf("rm *"), list[0].patterns)
        assertEquals("m1", list[0].messageID)
    }

    @Test
    fun parsesQuestions() {
        val body = """[{"id":"que_1","sessionID":"ses_1","questions":[{"header":"Pick","question":"Which?",
          "options":[{"label":"A","description":"first"}],"multiple":false,"custom":true}]}]"""
        val list = DtoMap.parseQuestions(body)
        assertEquals(1, list.size)
        assertEquals(1, list[0].questions.size)
        assertEquals("Pick", list[0].questions[0].header)
        assertEquals(1, list[0].questions[0].options.size)
        assertEquals("A", list[0].questions[0].options[0].label)
        assertEquals(true, list[0].questions[0].customAllowed)
        assertEquals(false, list[0].questions[0].multiple)
    }

    @Test
    fun parsesProvidersAgentsCommands() {
        val prov = """{"all":[{"id":"meta","name":"Meta","models":{"muse-spark-1.3":{"name":"Spark","limit":{"context":1048576}}}}],"default":{}}"""
        val ps = DtoMap.parseProviders(prov)
        assertEquals(1, ps.size)
        assertEquals(1, ps[0].models.size)
        assertEquals(1048576, ps[0].models[0].contextLimit)
        val ag = """[{"name":"build","description":"b","mode":"all"},{"name":"hidden-one","hidden":true}]"""
        val as_ = DtoMap.parseAgents(ag)
        assertEquals(1, as_.size)
        val cmds = """[{"name":"init","description":"d","template":"t","hints":[]}]"""
        assertEquals(1, DtoMap.parseCommands(cmds).size)
        assertEquals(listOf("a", "b"), DtoMap.parseToolIds("""["a","b"]"""))
}
}
