"""
leyes.py — Procedimiento paso a paso con leyes lógicas.

Trabaja sobre el árbol que ya genera tu parser (tuplas):
    ("var", "p") | ("const", True) | ("not", x) | (op, a, b)
    con op en: "and", "or", "xor", "imp", "iff"

La lógica solo usa la biblioteca estándar. Streamlit y pandas se importan
dentro de mostrar_procedimiento(), que es lo único que toca la interfaz.
"""

SIMBOLO = {"and": "∧", "or": "∨", "xor": "⊕", "imp": "→", "iff": "↔"}


# ============================================================
# UTILIDADES
# ============================================================
def formatear(n, raiz=True):
    """Árbol -> texto (misma notación que a_texto de la app)."""
    k = n[0]
    if k == "var":
        return n[1]
    if k == "const":
        return "1" if n[1] else "0"
    if k == "not":
        return "¬" + formatear(n[1], False)
    s = f"{formatear(n[1], False)} {SIMBOLO[k]} {formatear(n[2], False)}"
    return s if raiz else f"({s})"


def _neg(x):
    return ("not", x)


def _canon(n):
    """Forma canónica: ordena los operandos de ∧ ∨ ⊕ ↔ (conmutatividad)."""
    k = n[0]
    if k in ("var", "const"):
        return n
    if k == "not":
        return ("not", _canon(n[1]))
    hijos = [_canon(n[1]), _canon(n[2])]
    if k != "imp":
        hijos.sort(key=repr)
    return (k, *hijos)


def _iguales(a, b):
    return _canon(a) == _canon(b)


def _complementarios(a, b):
    return _iguales(a, _neg(b)) or _iguales(_neg(a), b)


def _aplanar(n, op):
    """(a ∨ b) ∨ c  ->  [a, b, c]"""
    if n[0] == op:
        return _aplanar(n[1], op) + _aplanar(n[2], op)
    return [n]


def _anidar(op, terminos):
    """[a, b, c] -> a op (b op c)"""
    t = terminos[-1]
    for x in reversed(terminos[:-1]):
        t = (op, x, t)
    return t


# ============================================================
# REGLAS (cada una devuelve (nuevo_nodo, nombre_de_la_ley) o None)
# ============================================================
# --- Grupo 1: eliminar ↔, ⊕, → -------------------------------
def _eliminar_iff(n):
    if n[0] == "iff":
        a, b = n[1], n[2]
        return (("and", ("imp", a, b), ("imp", b, a)),
                "Bicondicional (p ↔ q ≡ (p → q) ∧ (q → p))")


def _eliminar_xor(n):
    if n[0] == "xor":
        a, b = n[1], n[2]
        return (("and", ("or", a, b), _neg(("and", a, b))),
                "XOR (p ⊕ q ≡ (p ∨ q) ∧ ¬(p ∧ q))")


def _eliminar_imp(n):
    if n[0] == "imp":
        return ("or", _neg(n[1]), n[2]), "Condicional (p → q ≡ ¬p ∨ q)"


# --- Grupo 2: mover las negaciones hacia adentro --------------
def _doble_neg(n):
    if n[0] == "not" and n[1][0] == "not":
        return n[1][1], "Doble negación (¬¬p ≡ p)"


def _morgan(n):
    if n[0] == "not" and n[1][0] in ("and", "or"):
        k, a, b = n[1]
        if k == "and":
            return ("or", _neg(a), _neg(b)), "De Morgan (¬(p ∧ q) ≡ ¬p ∨ ¬q)"
        return ("and", _neg(a), _neg(b)), "De Morgan (¬(p ∨ q) ≡ ¬p ∧ ¬q)"


def _neg_constante(n):
    if n[0] == "not" and n[1][0] == "const":
        return ("const", not n[1][1]), "Negación de constante (¬1 ≡ 0, ¬0 ≡ 1)"


# --- Grupo 3: simplificar -------------------------------------
def _simplificar(n):
    k = n[0]
    if k not in ("and", "or"):
        return None
    a, b = n[1], n[2]
    s = SIMBOLO[k]
    otro = "and" if k == "or" else "or"
    s_otro = SIMBOLO[otro]
    dom = k == "or"          # constante que domina: 1 en ∨, 0 en ∧
    d, i = ("1", "0") if k == "or" else ("0", "1")

    for x, y in ((a, b), (b, a)):
        if x == ("const", dom):
            return x, f"Dominación (p {s} {d} ≡ {d})"
        if x == ("const", not dom):
            return y, f"Identidad (p {s} {i} ≡ p)"
    if _complementarios(a, b):
        return ("const", dom), f"Complemento (p {s} ¬p ≡ {d})"
    if _iguales(a, b):
        return a, f"Idempotencia (p {s} p ≡ p)"
    for x, y in ((a, b), (b, a)):
        if y[0] == otro and any(_iguales(x, z) for z in y[1:]):
            return x, f"Absorción (p {s} (p {s_otro} q) ≡ p)"


# --- Grupo 4: reagrupar para que dos términos queden juntos ----
def _reordenar(n):
    k = n[0]
    if k not in ("and", "or"):
        return None
    t = _aplanar(n, k)
    for i in range(len(t)):
        for j in range(i + 1, len(t)):
            if _iguales(t[i], t[j]) or _complementarios(t[i], t[j]):
                resto = [x for m, x in enumerate(t) if m not in (i, j)]
                nuevo = _anidar(k, resto + [(k, t[i], t[j])])
                if nuevo == n:
                    continue
                ley = "Asociativa" if resto + [t[i], t[j]] == t else "Conmutativa y asociativa"
                return nuevo, f"{ley} (agrupar términos para simplificar)"


# Prioridad: se prueba el grupo 1; si no aplica nada, el 2; y así. Tras cada
# paso se vuelve a empezar por el grupo 1.
GRUPOS = [
    [_eliminar_iff, _eliminar_xor, _eliminar_imp],
    [_doble_neg, _morgan, _neg_constante],
    [_simplificar],
    [_reordenar],
]


def _buscar(nodo, reglas):
    """Primera regla aplicable, recorriendo de adentro hacia afuera."""
    if nodo[0] not in ("var", "const"):
        for i in range(1, len(nodo)):
            r = _buscar(nodo[i], reglas)
            if r:
                hijo, ley = r
                return nodo[:i] + (hijo,) + nodo[i + 1:], ley
    for regla in reglas:
        r = regla(nodo)
        if r:
            return r
    return None


# ============================================================
# API PÚBLICA
# ============================================================
def derivar(arbol, max_pasos=60):
    """Devuelve [(ley, nodo), ...]. El primer elemento es la expresión original (ley=None)."""
    pasos = [(None, arbol)]
    actual = arbol
    for _ in range(max_pasos):
        for grupo in GRUPOS:
            r = _buscar(actual, grupo)
            if r:
                break
        else:
            break
        actual, ley = r
        pasos.append((ley, actual))
    return pasos


def mostrar_procedimiento(arbol):
    """Dibuja el procedimiento en Streamlit."""
    import pandas as pd
    import streamlit as st

    pasos = derivar(arbol)
    st.subheader("📐 Procedimiento con leyes lógicas")
    df = pd.DataFrame({
        "Paso": range(len(pasos)),
        "Expresión": [formatear(n) for _, n in pasos],
        "Ley aplicada": [ley or "Expresión original" for ley, _ in pasos],
    })
    st.table(df.set_index("Paso"))
    st.caption("La ley de cada fila es la que se usó para llegar a esa fila desde la anterior.")

    final = pasos[-1][1]
    if final == ("const", True):
        st.success("Se reduce a 1 → tautología (siempre verdadera).")
    elif final == ("const", False):
        st.error("Se reduce a 0 → contradicción (siempre falsa).")
    else:
        st.info(f"Forma simplificada: {formatear(final)}. Si no llegó a 1 ni a 0, "
                "no significa que sea contingencia: confía en la tabla de verdad.")
