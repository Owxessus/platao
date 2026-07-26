# Platão

<img src="assets/athena-coin.jpg" align="right" width="108" alt="Athena — o OS soberano de onde o Platão foi extraído">

**[English](README.md) · Português**

**Sua IA disse "pronto". O Platão faz as perguntas chatas que um sênior cético faria — antes de você confiar.**

Platão é um auditor de completude determinístico para código (e para o código que os seus agentes de IA escrevem). Ele não adivinha. Ele lê a árvore de sintaxe de verdade e responde perguntas como: *Isto está fiado, ou é código morto? O teste prova comportamento, ou só que o ficheiro importa? O "sucesso" é real, ou o pipeline é estruturalmente incapaz de falhar?* — exatamente as maneiras como um agente confiante-mas-errado deixa a obra silenciosamente incompleta.

Roda como CLI, hook de pre-commit, gate de CI e — o ponto — um **servidor MCP** que qualquer agente de código chama antes de dizer "terminei".

> **Dois produtos, uma filosofia.** O Platão tem um irmão, [Basanos](https://github.com/Owxessus/basanos) — a pedra-de-toque da fiação de UI (este botão chama um handler que existe de verdade e faz algo?). Eles são publicados separados e rodam sozinhos. Instale os dois e o Platão puxa o Basanos como um dos seus olhos. Veja [Rodando com o Basanos](#rodando-com-o-basanos).

---

## 30 segundos

```bash
npm install -g platao          # ou: pipx install platao
platao check src/service.py    # revê um ficheiro que a sua IA acabou de escrever
platao sweep .                 # varre o repo inteiro atrás de testes-placebo e código morto
```

```
Platão — src/service.py
  ⚠ [not_stub]          'process_order' só retorna sucesso sem fazer o trabalho
  • [swallowed_error]   except Exception engole o erro em silêncio (corpo é só `pass`)
  · [debt_tracked]      TODO sem rastreio — adicione dono ou ref de issue, ex. TODO(#123)

1 crítico · 1 preocupação · 1 nota
```

O `sweep` enxerga entre ficheiros também — um `from .db import connect` quebrado (`dangling_import`) ou um módulo que ninguém importa (`unwired`) só uma passada no repo inteiro pega.

Esse é o **chão determinístico, grátis e offline** — sem chave de API, sem rede, sem LLM. Roda igual toda vez e **não alucina**, porque *sabe* pela AST em vez de *adivinhar* por um modelo.

O **teto de juízo** opcional (`--judge`) adiciona a camada do sênior cético — veja [As duas camadas](#as-duas-camadas).

---

## Por que isto existe

Agentes de código falham de um jeito específico e reconhecível: **confiante mas errado, e silenciosamente incompleto.** Escrevem uma função que ninguém chama. Escrevem um teste que importa o alvo e não afirma nada. Emitem `event_completed` de uma função com corpo vazio. Dizem "pronto" — e você descobre três commits depois.

Cada verificação do Platão é uma pergunta que um dev sênior fica fazendo a um júnior depois de cada serviço. Capturamos esse checklist e fizemos uma máquina fazer as perguntas, toda vez, de graça.

**O enquadramento é "obrigação, não feature".** Um linter é algo que você desliga. Isto é mais parecido com um tribunal — você não desliga as perguntas só porque está com pressa. É esse o ponto: no instante em que vira opcional-quando-incomoda, o modo de falha que ele previne volta na hora.

---

## As duas camadas

O Platão é deliberadamente dividido para que a parte confiável esteja sempre ligada e a parte cara seja sempre a sua escolha.

| Camada | O que é | Custo | Rede | Alucina? |
|---|---|---|---|---|
| **Chão determinístico** (default) | Verificações AST/estáticas: fiado? órfão? teste real? placebo? débito rastreado? | **$0** | Offline | **Não** — lê a árvore |
| **Teto de juízo** (`--judge`, opt-in) | O sênior cético: *um crítico aprovaria isto ou desmontava em 30s?* | Sua conta de LLM | Seu provedor | Sim (é LLM) — por isso é conselho, nunca o gate |

O chão é o que torna o Platão confiável. O teto é o que o torna *esperto* sobre o que uma árvore não vê (um mock com cara de real, uma abstração sem cliente). **O teto é BYO-LLM** — você traz a sua própria chave de API ou um modelo local. O Platão te dá as *perguntas e o rubric*; você escolhe o cérebro. Veja [Custo e roteamento de modelo](#custo-e-roteamento-de-modelo).

---

## Linguagens

Os checks **profundos** do Platão — a análise de placebo/completude e o grafo de imports — leem a AST de Python, então rodam em `.py`. Em **qualquer outra linguagem** (JS, TS, Go, Ruby, PHP, Java, …) ele roda uma **camada universal**: os checks que valem em todo lado, casados de forma robusta sem parser — um `catch` vazio que engole o erro, `eval` dinâmico, um debugger esquecido no código, um `TODO` sem rastreio. Então `platao check app.ts` é real, não um no-op.

Essa camada de regex é de propósito rasa. Para análise **profunda** multi-linguagem há uma camada tree-sitter opcional:

```bash
pip install 'platao[deep]'   # ASTs reais para JS, TS, Go, Ruby, Java, Rust, PHP, C#, …
```

Com ela instalada, checks estruturais profundos rodam nessas linguagens também — `not_stub` (função de nome-de-ação com corpo genuinamente vazio, distinguida de uma declaração abstrata honesta) e `empty_test` (um `it(...)`/`test(...)` JS/TS cujo corpo não afirma nada — o cheiro do teste-fantasma). O core continua zero-dependência sem o extra; a camada poliglota de regex ainda cobre esses ficheiros. Mais checks profundos entram como queries tree-sitter ao lado destes. Hoje: profundo em Python (sempre) e nas linguagens da camada deep (com o extra), amplo em toda parte.

## As perguntas

Toda pergunta é `CODE` (determinística, grátis) ou `JUDGMENT` (precisa de LLM). **Todas são opt-in** — ligue os packs que quer, desligue os que não quer, adicione os seus. Os defaults são o conjunto de alto sinal e baixo falso-positivo — calibrados contra repos reais maduros (`requests`, `flask`, `click`, …) para ficar quieto em código idiomático e alto em defeito genuíno.

> **O que já vem hoje vs. o roadmap.** A lista abaixo é o checklist completo que orienta o Platão. Os checks **vivos nesta versão** são exatamente o que `platao list-checks` imprime — hoje o núcleo conectividade / placebo / robustez / higiene (`not_stub`, `dangling_import`, `unwired`, `swallowed_error`, `dangerous_dynamic`, `mutable_default`, `hardcoded_secret`, `debt_tracked`, `debug_leftover`, e os checks de teste-placebo), o `not_stub`/`empty_test` profundo para outras linguagens via `platao[deep]`, mais as nove perguntas de juízo `momo`. O resto é roadmap — cada um entra sob o mesmo gate de prova (ver [Contribuindo](#contribuindo--o-gate-rígido)). **Rode `platao list-checks` para o conjunto autoritativo na sua versão.**

### Determinísticas (CODE — grátis, offline)

**Está conectado?**
- `wired` — é chamado/importado, ou é código-ilha morto?
- `orphan_output` — o que ele produz (evento/export/retorno/endpoint) é consumido em algum lugar?
- `dangling_ref` — referencia coisas que existem de fato no repo?
- `api_exists` — chama métodos/campos que existem no alvo *real*, não só num mock?

**É real, ou placebo?**
- `has_effect_test` — um teste que **afirma comportamento** (importa + afirma), não só que importa/monta?
- `oracle_independent` — o teste checa um oráculo independente, não o auto-relato do próprio código?
- `negative_control` — existe caminho de falha testado — ele falha quando deveria?
- `can_fail` — o pipeline tem como falhar (raise / retorno de erro / ramo), ou sempre retorna sucesso?
- `not_stub` — a função anunciada realmente faz algo, não só `pass`/`return True`?
- `done_has_work` — "concluído/sucesso" é emitido depois de trabalho real, não de um corpo vazio?

**Aguenta?**
- `no_swallowed_error` — nenhum `except`/`catch` engolindo erro em silêncio?
- `fail_closed` — em gate/auth/validação, o erro nega (fechado), não permite (aberto)?
- `resource_cleanup` — fecha o que abriu (`with`/`finally`/`defer`)?

**Reproduz e entrega?**
- `deps_declared` — todo import de terceiro declarado no `requirements`/`package.json`?
- `no_hardcoded_secret` — nenhuma chave/token no código **ou** em log?
- `no_hardcoded_path` — caminhos de config/arg, não cravados?
- `atomic_write` — escrita de ficheiro atômica (temp+replace), não corruptível a meio?

**Higiene e débito**
- `no_debug_leftover` — nenhum `print`/`console.log`/`debugger` esquecido?
- `no_dangerous_dynamic` — nenhum `eval`/`exec`/`shell` sem validação de escopo?
- `debt_tracked` — todo atalho tem `TODO` rastreável, não só na sua cabeça?
- `typed_documented` — funções públicas têm tipos + docstring/JSDoc?
- `not_god_function` — função abaixo de ~120 linhas / um estágio lógico?

**Fiação (delegada ao Basanos, se instalado)**
- `ui_wired` — os controles deste painel chamam handlers que existem e fazem algo?

### Juízo (JUDGMENT — BYO-LLM, opt-in)

- `momo_scrutiny` — **a estrela.** *Um sênior cético aprovaria isto, ou desmontava em 30 segundos? O que ele ataca primeiro?*
- `real_or_mock` — é real, ou um mock com cara de real?
- `edge_cases` — vazio / nulo / limite / entrada grande / unicode / concorrente cobertos?
- `single_responsibility` — uma responsabilidade, ou uma god-function se formando?
- `reuse_over_create` — confirmou que nada já faz isso (sem duplicação)?
- `abstraction_earns_keep` — a abstração tem mais de um cliente?
- `simpler_version` — existe versão mais simples que resolve igual?
- `hidden_magic` — acoplamento/mágica escondida que ninguém explica?

**Adicione a sua em uma linha** (veja [Configuração](#configuração)). Importe o seu `CLAUDE.md` / `AGENTS.md` e o Platão transforma as suas regras da casa em perguntas.

---

## Modos de uso (roteie por onde o trabalho acontece)

Você escolhe como ele se encaixa, e pode rotear por complexidade — só determinístico para checagens baratas e rápidas; adicione a camada de juízo só em ficheiros complexos ou críticos.

| Modo | Comando / setup | Melhor para |
|---|---|---|
| **CLI** | `platao check <path>` · `platao sweep .` | Manual, "minha IA terminou de verdade?" |
| **Hook de pre-commit** | `platao install-hook` | Barrar um commit num concern crítico |
| **Gate de CI** | GitHub Action (`uses: Owxessus/platao@main`) | Falha o build em achados ≥ `--fail-on` (um ratchet "só-novos" está planeado) |
| **Servidor MCP** ⭐ | `platao mcp` | Qualquer agente (Claude Code, Cursor, …) chama antes de dizer "pronto" |
| **SDK** | `import platao` | Seu próprio tooling |

O **servidor MCP** é o ponto. Expõe duas tools — `platao_check` (audita um ficheiro ou diretório) e `platao_list_checks` — para que qualquer agente com MCP verifique o próprio trabalho antes de alegar conclusão, sem precisar de integração com editor. Instale o extra e rode:

```bash
pip install 'platao[mcp]'
platao mcp        # servidor stdio; aponte o seu agente para ele
```

Há um **agente de construir-e-auditar** completo e rodável em [`examples/agent/`](examples/agent/): um projeto Claude Code que liga Platão e Basanos como servidores MCP e dá ao agente uma regra — *construa, depois audite, depois corrija, e só então diga "pronto"*. Vem com ficheiros de demo quebrados de propósito para você ver as tools dispararem já na primeira rodada.

---

## Custo e roteamento de modelo

**O chão determinístico é $0, sempre, e roda em toda checagem.** Esta seção é só sobre a camada de juízo opt-in, que usa o LLM que você apontar — **você escolhe o modelo, e pode rotear por complexidade** (modelo barato ou só-chão para diffs simples; modelo premium para ficheiros críticos).

### O modelo de tokens (medido, reproduzível)

Um review de juízo envia: um preâmbulo curto + o ficheiro em revisão (limitado a **12.000 caracteres** — isso limita o seu pior custo) + as perguntas de juízo ativadas. Medido num ficheiro representativo de ~440 linhas com 12 perguntas ligadas:

- **Input:** ≈ 3.500 tokens
- **Output:** ≈ 750 tokens (uma linha por pergunta)

**Custo por review = `3500/1e6 × preço_in + 750/1e6 × preço_out`.** Encaixe o preço de qualquer provedor. Ficheiros pequenos custam ~40–50% disto; o teto de 12k chars é o limite.

### Tabela de referência (~10 tiers)

Preços de **2026-06-24**; preço de LLM deriva — **confirme as taxas atuais no seu provedor.** As linhas Anthropic são exatas (tabela oficial); as de terceiros são aproximadas e marcadas ≈.

| Tier | Modelo | $/1M in | $/1M out | **Custo / review** | 1.000 reviews |
|---|---|---|---|---|---|
| Local | Ollama (gemma/qwen/llama) | — | — | **$0** (seu hardware) | $0 |
| Ultra-barato | DeepSeek-V3.2 ≈ | ≈0,28 | ≈0,42 | ≈ $0,0013 | ≈ $1,3 |
| Barato | Gemini Flash-class ≈ | ≈0,10 | ≈0,40 | ≈ $0,0007 | ≈ $0,7 |
| Barato | GPT-mini-class ≈ | ≈0,15 | ≈0,60 | ≈ $0,0010 | ≈ $1,0 |
| Econômico | **Claude Haiku 4.5** | 1,00 | 5,00 | **$0,0073** | $7,3 |
| Médio | Qwen/Llama-70B hospedado ≈ | ≈0,40 | ≈0,40 | ≈ $0,0017 | ≈ $1,7 |
| Equilibrado | **Claude Sonnet 5** (intro) | 2,00 | 10,00 | **$0,0145** | $14,5 |
| Equilibrado | **Claude Sonnet 5** (padrão) | 3,00 | 15,00 | **$0,0218** | $21,8 |
| Premium | **Claude Opus 5** | 5,00 | 25,00 | **$0,0363** | $36,3 |
| Topo | **Claude Fable 5** | 10,00 | 50,00 | **$0,0725** | $72,5 |

Notas de total honestidade:
- **Cache não ajuda aqui.** O corpo do ficheiro muda a cada review; só o preâmbulo+perguntas (~500 tokens) é estável, abaixo do piso de cache. Nenhum desconto de cache alegado.
- Um review verboso (um parágrafo por pergunta) pode dobrar o custo de output. Ainda centavos.
- **Roteamento:** configure um modelo barato para `platao check` a cada save e um premium só para `--judge` em caminhos críticos, ou rode **só-chão** (grátis) e reserve o juízo para quando realmente quiser o olho do sênior.

---

## Configuração

### Juízo (opt-in, BYO-LLM)

A camada do sênior cético fica desligada até você pedir e apontar um modelo. É BYO-LLM — qualquer endpoint compatível com OpenAI (OpenAI, OpenRouter, DeepSeek, um Ollama local):

```bash
export PLATAO_JUDGE_MODEL=gpt-4o-mini          # seu modelo
export PLATAO_JUDGE_API_KEY=sk-...             # sua chave — o Platão lê do env, nunca armazena
export PLATAO_JUDGE_BASE_URL=https://api.openai.com/v1   # opcional; default é OpenAI
platao check src/service.py --judge
```

O juízo é **consultivo**: os achados aparecem mas **não mexem no exit code** — os checks determinísticos é que são o portão (você não reprova o CI por opinião de LLM). E se o modelo não puder ser alcançado, o Platão diz isso com um achado `judge_unverified` — nunca reporta "tudo certo" em silêncio.

### Ficheiro de config

Desligue checks específicos com um `.platao.json` na raiz do repo (zero-dependência, real hoje). Sem ficheiro = nada desligado:

```json
{ "disable": ["debt_tracked", "ui_marble_tokens"] }
```

Ao varrer uma árvore, o Platão anda por cima de diretórios vendorados e gerados por padrão — `node_modules`, `.venv`/`venv`, `site-packages`, `build`/`dist`, os caches, e pastas de código vendorado (`vendor`, `third_party`, `thirdparty`, …). Código que você não escreveu não é seu para auditar. (Aponte a tool direto numa dessas pastas para forçar.)

Rode `platao list-checks` para ver todos os ids que dá para desligar. Um `.platao.yml` mais rico (packs de perguntas, importar o seu `CLAUDE.md` como perguntas) está **planeado** — a forma que ele terá:

```yaml
# .platao.yml (planeado)
questions:
  packs: { connected: true, placebo: true, robustness: true, hygiene: true, judgment: false }
  disable: [typed_documented]
  import: [CLAUDE.md]      # transforme as suas regras da casa em perguntas
```

---

## Rodando com o Basanos

[Basanos](https://github.com/Owxessus/basanos) é um produto separado. Se estiver instalado, a pergunta `ui_wired` do Platão acende e delega a ele automaticamente — sem config. Se não estiver, a pergunta some sem barulho (feature-detect, nunca um erro). É o modelo "dois produtos, rodam juntos": cada um sozinho; instalados juntos, o Platão é o interrogador e o Basanos é o seu olho de fiação.

```bash
npm install -g platao basanos    # os dois → o Platão puxa o Basanos como olho
```

---

## Contribuindo — o gate rígido

**Leia [CONTRIBUTING.pt-BR.md](CONTRIBUTING.pt-BR.md) antes de abrir um PR.** Toda verificação contribuída passa por uma prova rigorosa ou não faz merge — sem exceção, forçado por CI:

1. **Determinística** — uma verificação `CODE` não usa LLM.
2. **Provada** — vem com `prove_effect` (pega o alvo num fixture que tem o defeito) **e** `negative_control` (fica quieta em código limpo — sem falso-positivo).
3. **Severidade declarada.**
4. **"Detectar mais fácil que produzir"** — a verificação que acha o problema tem de ser mais simples que o código que o tem. Um validador em que você não confia não sobe.

O CI roda a prova de cada verificação em todo PR. Sem prova, sem merge. Não é burocracia — *é* o produto. Um auditor de completude que aceitasse verificações não-provadas seria o seu próprio pior achado.

---

## De onde isto veio

O Platão é uma entidade extraída da **Athena**, um OS agêntico soberano construído sobre uma disciplina única: **anti-placebo, segura, determinística, com governança, auditável.** Na Athena, "você terminou de verdade?" não é um linter que você roda — é um reflexo que o sistema executa sobre si mesmo, toda vez que constrói algo, fiado a dezenas de entidades complementares que curam, gateiam, lembram e provam.

O que você tem em mãos é cerca de **1% disso** — a metade determinística de uma dessas entidades, doada por conta própria. Abrimos porque o modo de falha que ela previne — trabalho confiante, incompleto, não-verificado — é problema de todo mundo agora que agentes escrevem tanto do nosso código, e esta peça é genuinamente útil sozinha.

O resto — a orquestração do juízo, os gates de segurança, a memória, a auto-cura, a governança que decide o que um agente sequer tem permissão de fazer — é a parte que não é uma ferramenta. É uma arquitetura. Se as perguntas deste README te deixaram curioso sobre como fica quando um sistema as faz *a si mesmo*, esse é o instinto certo. Mais sobre isso quando estiver pronto.

Por ora: isto se sustenta sozinho. Use.

---

## Licença

MIT. Contribuições sob a mesma, mais o gate de prova do [CONTRIBUTING.pt-BR.md](CONTRIBUTING.pt-BR.md).
