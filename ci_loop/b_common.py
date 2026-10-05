import json,re
DISP={"python":"Python","javascript":"JavaScript","typescript":"TypeScript","java":"Java","cpp":"C++","csharp":"C#","go":"Go","rust":"Rust"}
FORMAT=("入出力の形式(厳守):\n"
"- 標準入力は、関数の引数を順に1つずつ、改行区切りで並べたものです。\n"
"- 各値の表記: 真偽値は true / false(小文字)。None は空文字(空行)。整数は 10、浮動小数点数はPythonのstr()と同じ表記(例: 10.0, 0.5, 1e-05)。文字列はそのまま(引用符なし)。\n"
"- リストは、1行目に要素数、2行目に要素を空白区切りで並べます。要素の表記は、文字列はそのまま、整数・浮動小数点数は上と同じ、None は None、真偽値は True / False。要素がリストや辞書のときは、Pythonのrepr表記(例: [1, 2], {'a': 1}, 文字列は引用符つき)。\n"
"- 辞書は、Pythonの表記({'a': 1})のまま1行で書きます。\n"
"- 標準出力も同じ規則で、関数の戻り値を1つ出力します。余計な文字列(入力を促すメッセージなど)は出力しないでください。\n")
def value_repr(value):
    if isinstance(value,bool): return "true" if value else "false"
    if isinstance(value,list): return f"{len(value)}\n"+" ".join(str(v) for v in value)
    if value is None: return ""
    return str(value)
def build_stdio_pairs(io_pairs):
    return [{"stdin":"\n".join(value_repr(a) for a in p["args"]),"expected_stdout":value_repr(p["expected"])} for p in io_pairs]
