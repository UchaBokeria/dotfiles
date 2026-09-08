package render

import (
	"container/list"
	"sync"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/domain"
)

// key identifies a rendered bubble. The theme generation is part of it so a
// re-themed palette invalidates the cache without anyone having to remember to
// clear it.
type key struct {
	id         string
	width      int
	maxBubble  int
	showSender bool
	generation int64
	// revision distinguishes the same message before and after an edit, a
	// receipt, or a reaction.
	revision string
}

// Cache memoises rendered bubbles.
//
// Scrolling a chat re-renders the visible window on every keystroke, and
// re-wrapping text that has not changed is the obvious waste to remove first.
type Cache struct {
	mu    sync.Mutex
	max   int
	items map[key]*list.Element
	order *list.List // front is most recently used
}

type entry struct {
	k     key
	lines []string
}

// NewCache returns a cache holding at most max entries.
func NewCache(max int) *Cache {
	if max <= 0 {
		max = 512
	}
	return &Cache{max: max, items: map[key]*list.Element{}, order: list.New()}
}

// Bubble renders a message, reusing a previous render when nothing that
// affects it has changed.
func (c *Cache) Bubble(m domain.Message, o Options) []string {
	k := key{
		id:         m.ID,
		width:      o.Width,
		maxBubble:  o.MaxBubble,
		showSender: o.ShowSender,
		generation: o.Styles.Generation,
		revision:   revisionOf(m),
	}

	c.mu.Lock()
	if el, ok := c.items[k]; ok {
		c.order.MoveToFront(el)
		lines := el.Value.(*entry).lines
		c.mu.Unlock()
		return lines
	}
	c.mu.Unlock()

	lines := Bubble(m, o)

	c.mu.Lock()
	defer c.mu.Unlock()
	if el, ok := c.items[k]; ok {
		c.order.MoveToFront(el)
		return el.Value.(*entry).lines
	}
	el := c.order.PushFront(&entry{k: k, lines: lines})
	c.items[k] = el
	for c.order.Len() > c.max {
		oldest := c.order.Back()
		c.order.Remove(oldest)
		delete(c.items, oldest.Value.(*entry).k)
	}
	return lines
}

// revisionOf changes whenever something that alters the rendering changes.
func revisionOf(m domain.Message) string {
	var b []byte
	b = append(b, m.Text...)
	b = append(b, byte(m.Delivery))
	if m.Edited {
		b = append(b, 'e')
	}
	if m.Revoked {
		b = append(b, 'r')
	}
	if m.Local {
		b = append(b, 'l')
	}
	b = append(b, m.QuotedText...)
	if m.Media != nil {
		b = append(b, m.Media.Filename...)
		b = append(b, m.Media.Caption...)
	}
	b = append(b, m.Err...)
	return string(b)
}

// Len is the number of cached renders.
func (c *Cache) Len() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.order.Len()
}

// Clear empties the cache.
func (c *Cache) Clear() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.items = map[key]*list.Element{}
	c.order.Init()
}
