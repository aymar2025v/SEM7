"""
mph_chd.py
Mini-implementación didáctica de una función hash perfecta mínima (MPHF)
al estilo CHD (compress-hash-displace) / hash-and-displace, para el
trabajo de investigación de la Práctica N.° 07 (SIS210, UNAP Puno).

Idea (resumen):
  1. Se reparten las n claves en r = ceil(n/lambda) cubetas con una función hash.
  2. Se ordenan las cubetas de mayor a menor tamaño.
  3. Para cada cubeta se busca un "piloto" p (entero pequeño) tal que las
     posiciones  pos(clave, p) = mix(h(clave) XOR p*K) mod m  de TODAS sus
     claves sean distintas entre sí y estén libres.
  4. Se guardan solo los pilotos (unos pocos bits por clave).
  5. Para que sea MÍNIMA (rango [0, n-1]) se usa m = ceil(n/alpha) con
     alpha < 1 (aquí 0.99) y las posiciones >= n se redirigen a los huecos
     libres < n mediante un arreglo pequeño (remap).

Uso:  python mph_chd.py
"""
import math
import random
import string
import sys
import time
from collections import Counter

MASK = (1 << 64) - 1
K = 0x9E3779B97F4A7C15


# ---------------------------------------------------------------- hashing --
def fnv1a_64(s: str) -> int:
    """FNV-1a de 64 bits (la misma familia usada en la Actividad 5 en C++)."""
    h = 14695981039346656037
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 1099511628211) & MASK
    return h


def mix64(x: int) -> int:
    """Finalizador de SplitMix64: dispersa bien los bits."""
    x = (x + K) & MASK
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & MASK
    return x ^ (x >> 31)


# ------------------------------------------------------------------ MPHF --
class MPHF:
    """Función hash perfecta mínima estática (estilo CHD)."""

    def __init__(self, claves, lam: float = 5.0, alpha: float = 0.99,
                 max_piloto: int = 2_000_000, base_hash=None):
        # base_hash: por defecto FNV-1a (portable y reproducible). Con
        # base_hash=lambda c: hash(c) & MASK se usa el hash nativo de Python
        # (más rápido, pero válido solo dentro del mismo proceso).
        self._h = base_hash or fnv1a_64
        claves = list(claves)
        assert len(set(claves)) == len(claves), "las claves deben ser únicas"
        self.n = n = len(claves)
        self.m = m = max(n, math.ceil(n / alpha))
        self.r = r = max(1, math.ceil(n / lam))
        hs = [self._h(c) for c in claves]

        # 1) cubetas
        cubetas = [[] for _ in range(r)]
        for h in hs:
            cubetas[mix64(h) % r].append(h)

        # 2) mayor a menor
        orden = sorted(range(r), key=lambda i: -len(cubetas[i]))

        # 3) búsqueda de pilotos
        ocupado = bytearray(m)
        self.pilotos = [0] * r
        for i in orden:
            cub = cubetas[i]
            if not cub:
                continue
            p = 0
            while True:
                if p > max_piloto:
                    raise RuntimeError("no se halló piloto; use otra lambda/alpha")
                add = (p * K) & MASK
                pos = [mix64(h ^ add) % m for h in cub]
                if len(set(pos)) == len(pos) and not any(ocupado[x] for x in pos):
                    for x in pos:
                        ocupado[x] = 1
                    self.pilotos[i] = p
                    break
                p += 1

        # 4) remap: posiciones >= n -> huecos libres < n
        libres = [x for x in range(n) if not ocupado[x]]
        altos = [x for x in range(n, m) if ocupado[x]]
        assert len(libres) == len(altos)
        self.remap = {a: l for a, l in zip(altos, libres)}

    def indice(self, clave: str) -> int:
        h = self._h(clave)
        p = self.pilotos[mix64(h) % self.r]
        pos = mix64(h ^ ((p * K) & MASK)) % self.m
        return self.remap.get(pos, pos) if pos >= self.n else pos

    # tamaño de la descripción (sin las claves ni los valores)
    def bits_por_clave(self):
        n = self.n
        ancho = max(1, math.ceil(math.log2(max(self.pilotos) + 1)))
        fijo = (self.r * ancho + len(self.remap) * math.ceil(math.log2(n))) / n
        # estimación con entropía de Shannon de los pilotos (cota inferior
        # práctica de lo que lograría una codificación comprimida, p. ej. CHD)
        cnt = Counter(self.pilotos)
        H = -sum(c / self.r * math.log2(c / self.r) for c in cnt.values())
        entropia = (self.r * H + len(self.remap) * math.ceil(math.log2(n))) / n
        if self.r < 2000:          # muestra de pilotos muy pequeña: sesgada
            entropia = float('nan')
        return fijo, entropia


# ------------------------- tabla de la guía (Actividad 2), para comparar --
class TablaHashChaining:
    UMBRAL = 0.75

    def __init__(self, m: int = 11):
        self._m, self._n = m, 0
        self._tabla = [[] for _ in range(m)]
        self._rehashes = 0

    def _hash(self, clave):
        return hash(clave) % self._m

    def insertar(self, clave, valor):
        idx = self._hash(clave)
        for i, (k, _) in enumerate(self._tabla[idx]):
            if k == clave:
                self._tabla[idx][i] = (clave, valor)
                return
        self._tabla[idx].append((clave, valor))
        self._n += 1
        if self._n / self._m > self.UMBRAL:
            self._rehash()

    def buscar(self, clave):
        for k, v in self._tabla[self._hash(clave)]:
            if k == clave:
                return v
        return None

    def _rehash(self):
        vieja = self._tabla
        self._m = self._siguiente_primo(self._m * 2)
        self._tabla = [[] for _ in range(self._m)]
        self._n = 0
        self._rehashes += 1
        for cadena in vieja:
            for k, v in cadena:
                self.insertar(k, v)

    @staticmethod
    def _siguiente_primo(n):
        def es_primo(x):
            return x > 1 and all(x % i for i in range(2, int(x ** 0.5) + 1))
        while not es_primo(n):
            n += 1
        return n

    @property
    def factor_carga(self):
        return self._n / self._m

    def celdas_vacias(self):
        return sum(1 for c in self._tabla if not c) / self._m

    def comparaciones_exito(self, claves):
        total = 0
        for c in claves:
            for j, (k, _) in enumerate(self._tabla[self._hash(c)], 1):
                if k == c:
                    total += j
                    break
        return total / len(claves)


# ---------------------------------------------------------------- pruebas --
def claves_aleatorias(n, rng, largo=8):
    s = set()
    while len(s) < n:
        s.add("".join(rng.choices(string.ascii_lowercase, k=largo)))
    return list(s)


def main():
    rng = random.Random(42)
    print("1) Prueba de corrección (bijección sobre [0, n-1])")
    for n in (10, 100, 1000, 10000):
        ks = claves_aleatorias(n, rng)
        f = MPHF(ks)
        idx = sorted(f.indice(k) for k in ks)
        assert idx == list(range(n)), "no es perfecta mínima"
        print(f"   n={n:>6}: OK, índices = permutación de 0..{n-1}")

    print("\n2) Construcción y espacio (lambda=5, alpha=0.99)")
    print(f"{'n':>8} {'t_const(s)':>11} {'bits/clave (fijo)':>18} {'bits/clave (entropía)':>22}")
    resultados = {}
    for n in (1_000, 10_000, 100_000):
        ks = claves_aleatorias(n, rng)
        t0 = time.perf_counter()
        f = MPHF(ks)
        t = time.perf_counter() - t0
        fijo, ent = f.bits_por_clave()
        resultados[n] = (ks, f, t)
        print(f"{n:>8} {t:>11.2f} {fijo:>18.2f} {ent:>22.2f}")

    print("\n3) Búsqueda vs. tabla con encadenamiento + rehashing (Actividad 2)")
    print(f"{'n':>8} {'alpha':>6} {'celdas vacías':>14} {'comp. éxito':>12} "
          f"{'us MPHF(FNV)':>13} {'us MPHF(hash)':>14} {'us chain':>9}")
    nativo = lambda c: hash(c) & MASK
    for n, (ks, f, _) in resultados.items():
        f2 = MPHF(ks, base_hash=nativo) if n <= 10_000 else None
        t = TablaHashChaining(m=11)
        for i, k in enumerate(ks):
            t.insertar(k, i)
        consultas = ks[:20000] if n > 20000 else ks
        reps = max(1, 200000 // len(consultas))

        def medir(fn):
            t0 = time.perf_counter()
            for _ in range(reps):
                for k in consultas:
                    fn(k)
            return (time.perf_counter() - t0) / (reps * len(consultas)) * 1e6

        us_fnv = medir(f.indice)
        us_nat = medir(f2.indice) if f2 else float('nan')
        us_ch = medir(t.buscar)
        print(f"{n:>8} {t.factor_carga:>6.2f} {t.celdas_vacias()*100:>13.1f}% "
              f"{t.comparaciones_exito(consultas):>12.2f} {us_fnv:>13.2f} "
              f"{us_nat:>14.2f} {us_ch:>9.2f}")

    print("\n4) Efecto de lambda (n=20000, alpha=0.99)")
    print(f"{'lambda':>7} {'t_const(s)':>11} {'bits/clave (fijo)':>18} {'bits/clave (entropía)':>22}")
    ks = claves_aleatorias(20_000, rng)
    for lam in (3, 4, 5, 6):
        t0 = time.perf_counter()
        f = MPHF(ks, lam=lam)
        t = time.perf_counter() - t0
        fj, en = f.bits_por_clave()
        print(f"{lam:>7} {t:>11.2f} {fj:>18.2f} {en:>22.2f}")


if __name__ == "__main__":
    sys.exit(main())
