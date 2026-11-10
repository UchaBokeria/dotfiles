package main
import (
 "fmt"
 "github.com/UchaBokeria/dotfiles/whatsapp/internal/vim"
 "github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
)
func main() {
 b:=vim.NewBuffer(); b.SetText("()"); b.SetCursor(vim.Pos{Line:0,Col:0})
 span,ok:=vim.TextObject(b,"paren",false)
 fmt.Printf("empty_inner_paren: ok=%v span=%+v text=%q\n",ok,span,b.Slice(span))
 vim.Apply(b,"delete",span,nil,0)
 fmt.Printf("after_delete_inner_paren=%q\n",b.Text())
 km:=vim.NewKeymap()
 km.Bind(vim.Normal,keys.MustParse("i"),vim.Target{Kind:vim.TargetAction,Name:"mode.insert"})
 km.Bind(vim.Normal,keys.MustParse("@"),vim.Target{Kind:vim.TargetAction,Name:"macro.play"})
 km.Bind(vim.Insert,keys.MustParse("<Esc>"),vim.Target{Kind:vim.TargetAction,Name:"mode.normal"})
 regs:=vim.NewRegisters(nil,false);regs.SetMacro('a',"iX<Esc>")
 e:=vim.NewEngine(km,regs,vim.Options{})
 var results []vim.Resolved
 for _,k:=range keys.MustParse("@a") {results=append(results,e.Feed(k)...)}
 literals:=0
 for _,r:=range results {if r.Literal!=nil {literals++};fmt.Printf("macro_result action=%q literal=%v motion=%q\n",r.Action,r.Literal,r.Motion)}
 fmt.Printf("macro_insert_literal_count=%d mode_before_caller_applies=%v\n",literals,e.Mode())
}
