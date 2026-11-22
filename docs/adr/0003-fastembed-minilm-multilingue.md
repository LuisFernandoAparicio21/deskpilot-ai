# ADR-0003: fastembed con MiniLM multilingüe

- **Estado:** aceptada
- **Fecha:** 2026-11-22

## Contexto

Los usuarios escriben en español y en inglés (9.62% de los tickets, consulta `09`; HU-04). El proyecto debe
funcionar sin llaves y con una base de solo 15 artículos.

## Decisión

Embeddings locales con fastembed y `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384
dimensiones, unos 241 MB, corta a 128 tokens). Los tests y el CI usan un `FakeEmbedder` determinista por hashing
de tokens, y el modelo se descarga una vez a `data/vectordb/models`.

## Alternativas

- **API de embeddings de un proveedor:** mejor calidad posible, pero exige llave y red.
- **Modelo solo en inglés:** más pequeño, pero falla con español.

## Consecuencias

- Funciona sin red tras la descarga; el contenedor lo trae en la imagen.
- Se calibró el umbral 0.33 con este modelo: mínimo dentro del dominio 0.428, máximo fuera 0.236. Cambiar de
  modelo obliga a recalibrar (nota en `config.yaml`).
- El truncado a 128 tokens es aceptable porque las secciones miden como máximo 735 caracteres (L12).

## Fuentes

`docs/sources.md`: fastembed y *FastEmbed Supported Models*. ODD L13 y L14.
