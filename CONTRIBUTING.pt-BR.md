# Contribuindo com o Platão — o gate de prova

**[English](CONTRIBUTING.md) · Português**

O Platão é um auditor de completude. Ele seria o seu próprio pior achado se aceitasse verificações que não provam funcionar. Então a contribuição aqui é governada por uma regra, forçada pelo CI:

**Uma verificação que não consegue provar a si mesma não faz merge.**

Não é burocracia. Provar uma verificação é a mesma disciplina que a ferramenta pede do seu código. Se parece pesado, esse é o ponto — é a cultura que a ferramenta existe para espalhar.

## O que toda verificação nova tem de trazer

Um pull request que adiciona ou altera uma verificação **precisa** incluir os quatro, ou o CI o reprova:

### 1. É determinística (para verificações CODE)
Uma verificação `CODE` não usa LLM, nem rede, nem aleatoriedade. Mesma entrada → mesma saída, sempre. Se a ideia genuinamente precisa de juízo, é uma verificação `JUDGMENT` (BYO-LLM) e vive no pack de juízo — regras diferentes, ainda precisa de rubric e exemplos.

### 2. `prove_effect` — pega o alvo
Um fixture de teste que **tem o defeito**, e uma asserção de que a sua verificação **dispara** nele. Se ela alega achar código-ilha, entregue um ficheiro que é código-ilha e prove que a verificação o reporta.

### 3. `negative_control` — fica quieta em código limpo
Um fixture que é **limpo** (não tem o defeito), e uma asserção de que a sua verificação **não dispara**. Uma verificação sem controle negativo é um gerador de falso-positivo esperando para acontecer. Esta é a metade que a maioria dos linters pula, e a metade que nós exigimos.

### 4. Severidade declarada
`low` | `medium` | `high`. Seja honesto. `high` é para defeitos que quebram comportamento, não para preferências de estilo.

## A lei: "detectar mais fácil que produzir"

O código que **detecta** o problema tem de ser mais simples que o código que **tem** o problema. Se verificar uma propriedade é tão difícil quanto acertá-la de primeira, a verificação não é confiável — um validador que você não consegue verificar é pior que nenhum. Se o seu detector é uma heurística de 300 linhas para pegar um cheiro de 10 linhas, ele vai errar em código real. Simplifique ou retire.

## Exemplo: a forma de uma boa verificação

```
checks/
  no_swallowed_error.py         # o detector (determinístico, uma regra clara)
  fixtures/
    swallowed_error__dirty.py   # TEM o defeito
    swallowed_error__clean.py   # NÃO tem — o controle negativo
  tests/
    test_no_swallowed_error.py  # prove_effect + negative_control
```

```python
def test_prove_effect():
    findings = run_check("no_swallowed_error", "fixtures/swallowed_error__dirty.py")
    assert any(f.id == "no_swallowed_error" for f in findings)   # pega

def test_negative_control():
    findings = run_check("no_swallowed_error", "fixtures/swallowed_error__clean.py")
    assert not any(f.id == "no_swallowed_error" for f in findings)  # e fica quieto
```

## CI

Em todo PR, o CI roda a prova de **cada** verificação — nova e existente. Uma verificação nova sem um `prove_effect` e um `negative_control` reprova o build. E também reprova uma verificação existente cujo controle negativo comece a disparar (uma regressão rumo a falsos-positivos).

## Adicionando perguntas ao catálogo

Perguntas novas são bem-vindas — o catálogo é feito para crescer até virar um "checklist de code review de sênior" curado pela comunidade. Uma pergunta genuinamente geral (algo que o *seu* tech lead sempre faz) é exatamente o que pertence aqui. O mesmo gate vale: perguntas `CODE` precisam das duas provas; perguntas `JUDGMENT` precisam de um prompt-rubric claro mais artefatos de exemplo mostrando o veredito.

## Licença

Ao contribuir você concorda que o seu trabalho é lançado sob a licença MIT do projeto.
