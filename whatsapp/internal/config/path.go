package config

import (
	"encoding"
	"fmt"
	"reflect"
	"sort"
	"strconv"
	"strings"
)

// textual reports whether a type carries its own string form - Duration and
// Size do. Those are structurally numbers but are written and read as text, so
// the walker must treat them as leaves rather than descending into them, and
// the formatter must ask them rather than printing the integer inside.
func textual(t reflect.Type) bool {
	return reflect.PointerTo(t).Implements(reflect.TypeOf((*encoding.TextUnmarshaler)(nil)).Elem())
}

// Get returns the value at a dotted path such as "ui.list_width", formatted the
// way :set would accept it back.
func (c *Config) Get(path string) (string, error) {
	f, err := c.field(path)
	if err != nil {
		return "", err
	}
	return format(f)
}

// Set assigns the value at a dotted path, parsing it into the field's type. An
// unknown path or an unparseable value is an error naming the path, so a typo
// at the : prompt says so instead of quietly doing nothing.
func (c *Config) Set(path, value string) error {
	f, err := c.field(path)
	if err != nil {
		return err
	}
	if err := assign(f, value); err != nil {
		return fmt.Errorf("%s: %w", path, err)
	}
	return nil
}

// Paths lists every settable dotted path, sorted. It backs :set completion and
// the settings picker.
func Paths() []string {
	var out []string
	walk(reflect.TypeOf(Config{}), "", &out)
	sort.Strings(out)
	return out
}

func walk(t reflect.Type, prefix string, out *[]string) {
	for i := 0; i < t.NumField(); i++ {
		sf := t.Field(i)
		tag := strings.Split(sf.Tag.Get("toml"), ",")[0]
		if tag == "" || tag == "-" {
			continue
		}
		name := tag
		if prefix != "" {
			name = prefix + "." + tag
		}
		if sf.Type.Kind() == reflect.Struct && !textual(sf.Type) {
			walk(sf.Type, name, out)
			continue
		}
		if sf.Type.Kind() == reflect.Map {
			// Keymaps are edited with :map, not :set.
			continue
		}
		*out = append(*out, name)
	}
}

func (c *Config) field(path string) (reflect.Value, error) {
	parts := strings.Split(path, ".")
	v := reflect.ValueOf(c).Elem()
	for depth, part := range parts {
		if v.Kind() != reflect.Struct {
			return reflect.Value{}, fmt.Errorf("%s: %q is not a section", path, parts[depth-1])
		}
		f, ok := fieldByTOMLTag(v, part)
		if !ok {
			return reflect.Value{}, fmt.Errorf("%s: no such setting (try :set with <Tab>)", path)
		}
		v = f
	}
	if v.Kind() == reflect.Struct && !textual(v.Type()) {
		return reflect.Value{}, fmt.Errorf("%s: names a section, not a setting", path)
	}
	return v, nil
}

func fieldByTOMLTag(v reflect.Value, tag string) (reflect.Value, bool) {
	t := v.Type()
	for i := 0; i < t.NumField(); i++ {
		if strings.Split(t.Field(i).Tag.Get("toml"), ",")[0] == tag {
			return v.Field(i), true
		}
	}
	return reflect.Value{}, false
}

func format(v reflect.Value) (string, error) {
	if m, ok := v.Interface().(encoding.TextMarshaler); ok {
		b, err := m.MarshalText()
		return string(b), err
	}
	switch v.Kind() {
	case reflect.String:
		return v.String(), nil
	case reflect.Bool:
		return strconv.FormatBool(v.Bool()), nil
	case reflect.Int, reflect.Int64:
		return strconv.FormatInt(v.Int(), 10), nil
	default:
		return "", fmt.Errorf("cannot render a %s", v.Kind())
	}
}

func assign(v reflect.Value, s string) error {
	if v.CanAddr() {
		if u, ok := v.Addr().Interface().(encoding.TextUnmarshaler); ok {
			return u.UnmarshalText([]byte(s))
		}
	}
	switch v.Kind() {
	case reflect.String:
		v.SetString(s)
	case reflect.Bool:
		b, err := strconv.ParseBool(s)
		if err != nil {
			return fmt.Errorf("%q is not a boolean (true or false)", s)
		}
		v.SetBool(b)
	case reflect.Int, reflect.Int64:
		n, err := strconv.ParseInt(s, 10, 64)
		if err != nil {
			return fmt.Errorf("%q is not a number", s)
		}
		v.SetInt(n)
	default:
		return fmt.Errorf("cannot set a %s", v.Kind())
	}
	return nil
}
