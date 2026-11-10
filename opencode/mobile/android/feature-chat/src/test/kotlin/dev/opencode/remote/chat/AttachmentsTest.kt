package dev.opencode.remote.chat

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Pure staging helpers (H2). Bitmap paths need a device — verified live instead. */
class AttachmentsTest {

    @Test
    fun dataUrlShape() {
        val url = Attachments.buildDataUrl("image/jpeg", byteArrayOf(1, 2, 3))
        assertTrue(url.startsWith("data:image/jpeg;base64,"))
    }

    @Test
    fun imageDetection() {
        assertTrue(Attachments.isImage("image/png"))
        assertTrue(Attachments.isImage("image/jpeg"))
        assertTrue(!Attachments.isImage("application/pdf"))
        assertTrue(!Attachments.isImage(""))
    }

    @Test
    fun qualityAndDimBounds() {
        assertEquals(85, Attachments.jpegQuality(1))
        assertEquals(70, Attachments.jpegQuality(2))
        assertEquals(1600, Attachments.targetDim(1600))
        assertEquals(4096, Attachments.targetDim(99_999))
        assertEquals(320, Attachments.targetDim(10))
    }

    @Test
    fun corruptImageReturnsNull() {
        assertNull(Attachments.compressImage(byteArrayOf(0, 1, 2, 3), 1600, 2))
        assertNull(Attachments.compressImage(byteArrayOf(), 1600, 2))
    }
}
