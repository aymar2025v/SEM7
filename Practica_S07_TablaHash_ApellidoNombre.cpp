
// Compilar:  g++ -std=c++17 -O2 -Wall -Wextra Practica_S07_TablaHash_ApellidoNombre.cpp -o practica07
// Ejecutar:  ./practica07      (en Windows: .\practica07)

#include <chrono>
#include <cstdint>
#include <iostream>
#include <random>
#include <string>
#include <unordered_map>
#include <vector>

using Clock = std::chrono::steady_clock;

struct HashFNV
{
    std::size_t operator()(const std::string &s) const
    {
        std::uint64_t hash = 14695981039346656037ULL; // FNV offset basis
        for (unsigned char c : s)
        {
            hash ^= c;
            hash *= 1099511628211ULL; // FNV prime
        }
        return static_cast<std::size_t>(hash);
    }
};

struct Resultado
{
    double ms = 0; // tiempo promedio (insertar + buscar todas las claves)
    double load_factor = 0;
    std::size_t buckets = 0;    // cantidad de buckets de la tabla
    std::size_t vacios = 0;     // buckets sin ninguna clave
    std::size_t max_bucket = 0; // claves en el bucket más lleno (peor cadena)
    long long checksum = 0;     // evita que el compilador elimine las búsquedas
};

template <typename Hash>
Resultado benchmarkHash(const std::vector<std::string> &claves, int repeticiones)
{
    Resultado res;
    double total_ms = 0.0;

    for (int r = -1; r < repeticiones; r++)
    { // r = -1: calentamiento
        std::unordered_map<std::string, int, Hash> mapa;
        mapa.reserve(claves.size());

        auto t0 = Clock::now();
        for (std::size_t i = 0; i < claves.size(); i++)
        {
            mapa[claves[i]] = static_cast<int>(i);
        }
        long long suma = 0;
        for (const auto &k : claves)
        {
            suma += mapa.find(k)->second;
        }
        double ms = std::chrono::duration<double, std::milli>(Clock::now() - t0).count();

        if (r >= 0)
            total_ms += ms;

        if (r == repeticiones - 1)
        { // estadísticas de la última corrida
            res.load_factor = mapa.load_factor();
            res.buckets = mapa.bucket_count();
            for (std::size_t b = 0; b < mapa.bucket_count(); b++)
            {
                std::size_t tam = mapa.bucket_size(b);
                if (tam == 0)
                    res.vacios++;
                if (tam > res.max_bucket)
                    res.max_bucket = tam;
            }
            res.checksum = suma;
        }
    }

    res.ms = total_ms / repeticiones;
    return res;
}

void mostrar(const char *nombre, std::size_t n, const Resultado &r)
{
    std::cout << nombre << "  n=" << n
              << "  tiempo=" << r.ms << " ms"
              << "  load_factor=" << r.load_factor << '\n'
              << "            buckets=" << r.buckets
              << "  vacios=" << r.vacios
              << "  max_en_bucket=" << r.max_bucket
              << "  checksum=" << r.checksum << "\n\n";
}

int main()
{
    // Generar 50 000 claves aleatorias de 8 letras minúsculas
    std::mt19937 rng(42);
    const std::string letras = "abcdefghijklmnopqrstuvwxyz";
    std::vector<std::string> claves;
    for (int i = 0; i < 50000; i++)
    {
        std::string s(8, ' ');
        for (char &c : s)
            c = letras[rng() % 26];
        claves.push_back(s);
    }

    const int REPETICIONES = 10;
    std::cout << "Benchmark con " << claves.size() << " claves, promedio de "
              << REPETICIONES << " corridas\n\n";

    Resultado r_std = benchmarkHash<std::hash<std::string>>(claves, REPETICIONES);
    Resultado r_fnv = benchmarkHash<HashFNV>(claves, REPETICIONES);

    mostrar("std::hash", claves.size(), r_std);
    mostrar("FNV-1a   ", claves.size(), r_fnv);

    double ratio = r_std.ms / r_fnv.ms;
    std::cout << "Ratio (std::hash / FNV-1a): " << ratio << "x\n";
    if (ratio > 1.0)
        std::cout << "-> FNV-1a fue mas rapida.\n";
    else
        std::cout << "-> std::hash fue mas rapida (o igual).\n";

    return 0;
}

// salida

// Benchmark con 50000 claves, promedio de 10 corridas

// std::hash  n=50000  tiempo=3.98376 ms  load_factor=0.939832
//             buckets=53201  vacios=20985  max_en_bucket=8  checksum=1249975000

// FNV-1a     n=50000  tiempo=4.24391 ms  load_factor=0.939832
//             buckets=53201  vacios=20662  max_en_bucket=8  checksum=1249975000

// Ratio (std::hash / FNV-1a): 0.9387x
// -> std::hash fue mas rapida (o igual).