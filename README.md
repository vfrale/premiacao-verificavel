# Premiação verificável

Protótipo do TCC *Verificabilidade criptográfica de aleatoriedade em mecanismos
digitais de premiação* (Victor Fritsch Ribeiro, Ciência da Computação, UNIJUÍ).

O repositório contém:

| Diretório | Conteúdo |
|---|---|
| `premiacao/` | Lado do operador: protocolo *provably fair* (compromisso SHA-256 e HMAC-SHA256), conversão sem viés por descarte e os dois mecanismos simulados (sorteio entre 100 participantes e caixa de recompensa 50/30/15/4/1). |
| `verificador/` | Verificador independente, de linha de comando. Não importa nenhum módulo de `premiacao/`. |
| `avaliacao/` | Experimentos do Capítulo 4: geradores G-HMAC, G-MT e G-RANDU; testes da Portaria SPA/MF nº 722/2024 (P1–P7); regra de decisão; aderência; cenários de manipulação C0–C5; integração com o NIST STS 2.1.2. |
| `tests/` | 43 testes automatizados (pytest). |

## Instalação

Requer Python 3.12 ou superior.

```console
python -m pip install -r requirements.txt
python -m pytest
```

## Uso do protótipo e do verificador

```console
python -m premiacao --mecanismo caixa --eventos 10 --saida registro.json
python -m verificador registro.json      # código de saída: 0 válido, 1 inválido, 2 malformado
```

O registro público (`registro.json`) contém o compromisso, a semente revelada,
a semente do participante, o mecanismo declarado e os eventos `[n, resultado]`.

## Experimentos

```console
python -m avaliacao.executar portaria  --sequencias 1000 --saida resultados
python -m avaliacao.executar aderencia --ciclos 1000 --eventos 10000 --saida resultados
python -m avaliacao.executar cenarios  --execucoes 1000 --saida resultados
python -m avaliacao.executar nist      --sequencias 1000 --sts /caminho/sts-2.1.2 --saida resultados
```

Cada execução grava `resultados/<experimento>.json` e acrescenta as sementes
usadas em `resultados/sementes.jsonl`. O experimento `nist` grava os arquivos
binários (10^6 bits por sequência) e, se `--sts` apontar para o STS 2.1.2
compilado, executa o programa `assess` e aplica a regra de decisão ao
`finalAnalysisReport.txt`. O STS não é redistribuído aqui: obtenha-o no sítio
do NIST (SP 800-22 Rev. 1a) ou na cópia pública
`github.com/terrillmoore/NIST-Statistical-Test-Suite`, usada no TCC.

Com vários diretórios em `--sts` (cópias independentes do STS compilado), as
sequências são divididas em partes disjuntas avaliadas em paralelo e os
relatórios são combinados pela soma exata das contagens. Os resultados do TCC
foram obtidos com duas cópias, uma por fonte de cada vez:

```console
python -m avaliacao.executar nist --sequencias 1000 --fontes G-HMAC G-MT \
    --rotulo hmac_mt --sts sts-1 sts-2 --saida resultados
python -m avaliacao.executar nist --sequencias 1000 --fontes G-RANDU-R31 \
    --rotulo randu_r31 --sts sts-1 sts-2 --saida resultados
python -m avaliacao.executar nist --sequencias 1000 --fontes G-RANDU-R16 \
    --rotulo randu_r16 --sts sts-1 sts-2 --saida resultados
```

Os arquivos `.bin` não são versionados (cerca de 125 MB por amostra), mas
podem ser regenerados a partir das sementes registradas.

## Análises do Capítulo 6

Partem do registro de sementes em `resultados/` e não exigem o STS:

```console
python -m avaliacao.executar aderencia --fontes G-HMAC --rotulo hmac_suplementar --saida resultados
python -m avaliacao.reanalise_p7     --saida resultados   # P7 com valor-p exato e aleatorizado
python -m avaliacao.analise_cenarios --saida resultados   # IC 95%, vantagem em C4, conferência de C3
python -m avaliacao.previsao_mt      --saida resultados   # G-MT previsto a partir de 624 saídas
python -m avaliacao.diagnostico_r16  --saida resultados   # variância por bloco no RANDU R16
python -m avaliacao.figuras --saida resultados --destino figuras/cenarios-c4.pdf
```

O teste P7 usado nos resultados do TCC é `portaria.p7_duplicacao`, que
calcula o valor-p pela distribuição exata do número de colisões e o
aleatoriza pela transformação integral, de modo que seja uniforme sob H0. O
módulo mantém também `portaria.p7_duplicacao_poisson`, com aproximação de
Poisson e valor-p bilateral discreto, que não tem essa propriedade e foi a
versão usada na execução registrada em `portaria.json`. Por isso, os valores
de P7 apresentados no TCC estão em `portaria_p7_corrigido.json`, gerado por
`reanalise_p7` a partir das mesmas sementes, depois de conferir que a versão
de Poisson reproduz exatamente `portaria.json`.


## Licença

Código distribuído sob a licença MIT (arquivo `LICENSE`).
