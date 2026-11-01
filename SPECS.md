# Especificação de Projeto: Bot Rastreador de Preços de Livros com Fallback de IA

Objetivo: Acompanhar os preços de produtos guardar o menor preço, e conseguir sempre responder qual o menor preço atual dentre as plataformas avaliadas,
e responder se o preço atual está ou não abaixo da média

## 1. Visão Geral do Projeto
Criar um script em **Python** para monitorar preços de livros em três plataformas: **Amazon**, **Mercado Livre** e **Estante Virtual**. O script deve rodar periodicamente (via GitHub Actions), extrair os preços atuais, calcular métricas estatísticas, atualizar um arquivo consolidado, registrar histórico inteligente (apenas quando houver variação superior a R$ 1,00) e enviar alertas no **Telegram** se necessário.

Devem ser utilizados dois arquivos de dados locais:
1. `consolidado.json`: Contém a "foto" mais recente de todos os produtos e links monitorados (usado pelo dashboard). 
2. `historico.json`: Contém o log temporal que **só recebe uma nova entrada** se o preço de um link variar R$ 1,00 ou mais em relação ao último registro salvo.
    - deve guardar separado por plataforma (quero poder sempre ver o melhor preço naquela plataforma)
    - deve guardar também um com o produto escolhido (o mais barato)

A estante virtual costuma ter frete, some sempre R$ 16,00 ao valor obtido a não ser que esteja claramente escrito como frete gratis.

Nas configurações existe um BLACKLIST_BOOKS, com os titulos de livros a serem descartados quando na busca (Estante virtual e mercado livre)

---

## 2. Estrutura de Configuração dos Produtos (Config.py)

O script deve ser configurado utilizando a seguinte estrutura de classes e dados:

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class Plataforma(Enum):
    AMAZON = "amazon"
    MERCADO_LIVRE = "mercado_livre"
    ESTANTE_VIRTUAL = "estante_virtual"

@dataclass
class LinkConfig:
    url: str
    plataforma: Plataforma
    pesquisa: bool = False
    top_n: int = 1
    comentario: str = ""

@dataclass
class Produto:
    nome: str
    prioridade: int  # 1 é o mais alto
    links: List[LinkConfig]
    id: str  # estável e único; usado como chave do histórico
    comentario: str = ""
    porcentagem_alvo: float = 0.20

# Funções auxiliares / Atalhos para declaração limpa
def AmazonLink(url: str, comentario: str = "") -> LinkConfig:
    return LinkConfig(url=url, plataforma=Plataforma.AMAZON, comentario=comentario)

def MercadoLink(url: str, pesquisa: bool = False, top_n: int = 3, comentario: str = "") -> LinkConfig:
    return LinkConfig(url=url, plataforma=Plataforma.MERCADO_LIVRE, pesquisa=pesquisa, top_n=top_n if pesquisa else 1, comentario=comentario)

def EstanteLink(url: str, pesquisa: bool = False, top_n: int = 5, comentario: str = "") -> LinkConfig:
    return LinkConfig(url=url, plataforma=Plataforma.ESTANTE_VIRTUAL, pesquisa=pesquisa, top_n=top_n if pesquisa else 1, comentario=comentario)

# Exemplo de Lista de Produtos a Monitorar
PRODUTOS = [
    Produto(
        id='roma-greg-woolf',
        nome='Roma: A história de um império - Greg Woolf',
        prioridade=1,
        comentario='É o primeiro compre logo',
        porcentagem_alvo=0.1, # 10%, opcional padrão e 20%
        links=[
            AmazonLink(
                'https://www.amazon.com.br/dp/8531613930',
                comentario="Link direto"
            ),
            MercadoLink(
                'https://lista.mercadolivre.com.br/roma-a-historia-de-um-imperio',
                pesquisa=True,
                top_n=3
            ),
            EstanteLink(
                'https://www.estantevirtual.com.br/busca?q=roma-a-historia-de-um-imperio-greg-woolf',
                pesquisa=True,
                top_n=5
            )
        ]
    )
]
```

Quero duas ordenações nos produtos: por prioridade e pela ordem original no array, além e claro de ordenação de preço (maior e menor),
 Titulo (A e Z), e % de Desconto (Maior e menor)

## Regras para envio de notificação via Telegram

- Padrão: 20% abaixo da mediana
- Pode ser configurado manualmente em cada produto
- O envio por preço abaixo da mediana só ocorre depois de registrar ao menos **4 coletas válidas**
- Também sempre enviamos a notificação se for o menor preço registrado 
    - Nesse caso, a partir da segunda coleta válida, se o preço for pelo menos R$ 0,70 menor que o primeiro preço válido



## Excecução

- O código será executado no github actions (mas deve ser executavel em shell simples também)
    on:
    schedule:
        # Roda às 0, 2, 9, 12, 15, 18 e 21 horas UTC 
        # (Que correspondem a 21h, 23h, 6h, 9h, 12h, 15h e 18h de Brasília)
        - cron: '0 0,2,9,12,15,18,21 * * *'

- O "dashboard" será apenas para consulta e será disponibilizado via github pages (publico)
- Os códigos de scrapping devem ter a mesma interface/protocolo para as 3 plataformas
- Os códigos de scrapping devem ser separados do restante da aplicação

## Fazes

- Fase 1: apenas coleta e apresentação somente com a AMAZON (mas já com estrutura de dados pronta para atender as prox. fases)
- Fase 2: envio de notificação via Telegram
- Fase 3: implementação das outras plataformas (Mercado livre e Estante virtual)

## Arquivos


Consolidado
```json
{
  "ultima_atualizacao": "2026-11-01T15:00:00-03:00",
  "estatisticas_gerais": {
    "total_produtos": 12,
    "produtos_com_preco": 10,
    "produtos_com_falha": 3
  },
  "produtos": [
    {
      "id": "roma-greg-woolf",
      "nome": "Roma: A História de um Império — Greg Woolf",
      "prioridade": 1,
      "porcentagem_alvo": 0.10,
      "capa_url": "https://m.media-amazon.com/images/I/71Xxxx...jpg",
      "comentario": "É o primeiro compre logo",
      "contador_falhas": 0,
      "metricas_atuais": {
        "menor_preco_geral": 49.90,
        "plataforma_vencedora": "estante_virtual",
        "media": 52.27,
        "mediana": 52.00
      },
      "links": [
        {
          "plataforma": "amazon",
          "url": "https://www.amazon.com.br/dp/8531613930",
          "pesquisa": false,
          "preco_atual": 52.00,
          "titulo": "Roma: A história de um império",
          "capa_url": "https://m.media-amazon.com/images/I/71Xxxx.jpg",
          "erros_consecutivos": 0,
          "erro": null,
          "status": "sucesso"
        },
        {
          "plataforma": "mercado_livre",
          "url": "https://lista.mercadolivre.com.br/roma-a-historia-de-um-imperio",
          "pesquisa": true,
          "preco_atual": 54.90,
          "top_n_resultados": [
            {"titulo": "Roma A Historia De Um Imperio", "preco": 54.90, "escolhido": true, "url": "..."},
            {"titulo": "Livro Roma A Historia De Um Imperio Greg Woolf", "preco": 60.00, "escolhido": false, "url": "..."},
            {"titulo": "Roma Império - Greg Woolf (Novo)", "preco": 65.00, "escolhido": false, "url": "..."}
          ],
          "status": "sucesso"
        },
        {
          "plataforma": "estante_virtual",
          "url": "https://www.estantevirtual.com.br/busca?q=roma-a-historia-de-um-imperio-greg-woolf",
          "pesquisa": true,
          "preco_atual": 49.90,
          "extras": {"valor_sem_frete": 33.90, "frete_aplicado": 16.00, "frete_presumido": true},
          "top_n_resultados": [
            {"titulo": "Roma A História de Um Império", "valor_sem_frete": 33.90, "preco_total": 49.90, "escolhido": true, "url": "..."},
            {"titulo": "Roma: A Historia de um Imperio", "valor_sem_frete": 35.00, "preco_total": 51.00, "escolhido": false, "url": "..."}
          ],
          "status": "sucesso"
        }
      ]
    }
  ]
}
```


Historico
```json
{
  "roma-greg-woolf": {
    "vencedor_geral": [
      {
        "timestamp": "2026-11-01T09:00:00-03:00",
        "preco": 48.00,
        "plataforma": "amazon",
        "url": "https://www.amazon.com.br/dp/8531613930"
      },
      {
        "timestamp": "2026-11-01T15:00:00-03:00",
        "preco": 49.90,
        "plataforma": "estante_virtual",
        "url": "https://www.estantevirtual.com.br/busca?q=roma-a-historia-de-um-imperio-greg-woolf"
      }
    ],
    "por_plataforma": {
      "amazon": [
        {
          "timestamp": "2026-11-01T09:00:00-03:00",
          "preco": 48.00,
          "url": "https://www.amazon.com.br/dp/8531613930"
        },
        {
          "timestamp": "2026-11-01T15:00:00-03:00",
          "preco": 52.00,
          "url": "https://www.amazon.com.br/dp/8531613930"
        }
      ],
      "mercado_livre": [
        {
          "timestamp": "2026-11-01T15:00:00-03:00",
          "preco": 54.90,
          "url": "https://lista.mercadolivre.com.br/roma-a-historia-de-um-imperio"
        }
      ],
      "estante_virtual": [
        {
          "timestamp": "2026-11-01T15:00:00-03:00",
          "preco": 49.90,
          "url": "https://www.estantevirtual.com.br/busca?q=roma-a-historia-de-um-imperio-greg-woolf"
        }
      ]
    },
    "por_link": {
      "https://www.amazon.com.br/dp/8531613930": [
        {
          "timestamp": "2026-11-01T09:00:00-03:00",
          "preco": 48.00,
          "plataforma": "amazon"
        },
        {
          "timestamp": "2026-11-01T15:00:00-03:00",
          "preco": 52.00,
          "plataforma": "amazon"
        }
      ]
    }
  }
}
```


## Etapas da Fase 1

A Fase 1 entrega a coleta de preços da Amazon e a apresentação dos dados, deixando os formatos preparados para incluir Mercado Livre e Estante Virtual depois. Telegram fica para a Fase 2.

1. Definir e validar a configuração dos produtos
   - Implementar em Python as classes Plataforma, LinkConfig e Produto, além dos atalhos de configuração.
   - Incluir um id explícito, estável e único para cada produto e o campo porcentagem_alvo.
   - Validar os dados de configuração e considerar somente links da Amazon nesta fase.
2. Implementar o coletor da Amazon
   - Manter o código de scraping separado do restante da aplicação, com uma interface comum que possa ser implementada pelas outras plataformas nas fases seguintes.
   - Para cada link Amazon, obter o preço atual e, quando disponível, metadados úteis para apresentação, como título e capa.
   - Registrar sucesso ou falha por link, sem impedir a coleta dos demais produtos.
3. Montar o processamento dos preços
   - Associar os resultados coletados aos produtos e calcular a média, a mediana, o menor preço atual e a plataforma vencedora.
   - Preparar estruturas para múltiplos resultados de pesquisa (top_n_resultados), embora a coleta da Fase 1 use apenas Amazon.
   - Representar estados sem preço válido ou com erro de coleta, sem inventar valores.
4. Persistir os arquivos de dados
   - Gerar consolidado.json com horário da atualização, estatísticas gerais, produtos, métricas e estado de cada link.
   - Manter historico.json separado por produto, com histórico geral e por plataforma.
   - Acrescentar registro histórico de link apenas quando o preço variar mais de R$ 1,00 em relação ao último registro salvo. Como a Fase 1 coleta apenas Amazon, o histórico por plataforma inicialmente terá essa plataforma.
   - Definir claramente como tratar a primeira coleta, preços ausentes e variações exatamente iguais a R$ 1,00.
5. Criar a apresentação para consulta
   - Criar uma página estática que lê `consolidado.json` e `historico.json` no navegador.
   - Exibir preços, status por link, média, mediana, plataforma vencedora e histórico do vencedor geral.
   - Permitir busca e ordenação por ordem original, prioridade, preço crescente/decrescente, título A-Z/Z-A e percentual abaixo da mediana atual.
   - Mostrar valores ausentes sem inventar preços e manter a página compatível com publicação em subdiretório do GitHub Pages.
6. Preparar a execução periódica e manual
   - Configurar GitHub Actions para execução manual, em pushes para `main` e no cron especificado.
   - Restaurar e salvar `consolidado.json`, `historico.json` e `erros_consecutivos.json` no cache de Actions entre execuções.
   - Gerar o diretório `site/` com arquivos estáticos e dados para publicar pelo GitHub Pages.
   - Para pré-visualizar localmente, executar `python build_site.py` e `python -m http.server --directory site`.
   - Nas configurações do repositório, selecionar GitHub Actions como origem do GitHub Pages.
7. Verificar o fluxo completo
   - Validar a configuração, os resultados de sucesso e erro, os cálculos e a atualização dos JSON.
   - Conferir que os arquivos gerados correspondem aos formatos definidos e que a consulta funciona com dados incompletos.
   - Não implementar envio ao Telegram nem coletores das outras plataformas nesta fase.

### Regras de persistência

- Cada produto tem um `id` explícito, estável e único na configuração; o mesmo ID é usado no consolidado e como chave em `historico.json`.
- `produtos_com_preco` conta produtos com ao menos um preço válido; `produtos_com_falha` conta produtos sem preço válido em pelo menos uma plataforma esperada. Esses totais podem se sobrepor.
- `contador_falhas` no produto incrementa uma vez por execução quando pelo menos uma plataforma esperada não tem nenhum link com preço válido; volta a zero quando todas as plataformas esperadas têm preço. O contador por URL em `erros_consecutivos.json` é independente.
- Em `historico.json`, `por_link` guarda preços por URL; `por_plataforma` guarda o menor preço válido daquela plataforma na execução; `vencedor_geral` guarda o menor preço válido entre as plataformas. Os registros de plataforma e vencedor também guardam a URL que originou o preço.
- O primeiro preço válido sempre é registrado. Depois, um novo evento só é gravado quando a diferença absoluta para o último preço salvo for estritamente maior que R$ 1,00. Diferença igual a R$ 1,00 não gera evento.
- Preço ausente ou falha de coleta não apaga o último evento nem adiciona preço ao histórico. No consolidado, o preço e as métricas sem valor são `null`.
- Os timestamps são gerados no fuso `America/Sao_Paulo`. Os arquivos são escritos como JSON válido, sem comentários, e substituídos por gravação temporária.

## Estratégia de intervalo e retry na Amazon

- Esperar em média 12 segundos entre a coleta de produtos consecutivos, com jitter de ±20% (9,6 a 14,4 segundos).
- Em falhas temporárias de rede, respostas HTTP 408/429/5xx, resposta HTTP 403 identificada como CAPTCHA, CAPTCHA/Robot Check ou página de produto sem preço, fazer até 2 retries além da tentativa inicial.
- Aplicar espera base de 5 e 10 segundos antes dos dois retries, também com jitter de ±20%.
- Aplicar os dois retries também quando a resposta identificar CAPTCHA/Robot Check; se as três tentativas falharem, registrar a falha e seguir para o próximo produto após o intervalo normal.
- Manter um contador persistente por produto caso o produto não tenha o preço de alguma das plataformas na ultima execução.
- Manter um contador persistente por URL em `erros_consecutivos.json`: incrementar uma vez quando a coleta termina sem sucesso após as tentativas permitidas e zerar quando a coleta do link tiver sucesso.
- Rotacionar entre os perfis de navegador `chrome`, `firefox` e `safari` do `curl-cffi`, que fornecem User Agents associados aos respectivos fingerprints; evitar User Agents manuais que não correspondam ao fingerprint.
- Não trocar IP/proxy nem responder automaticamente ao desafio CAPTCHA.
- Intervalos e retries reduzem a frequência das requisições, mas não garantem que a Amazon não apresente bloqueios.

## Implementação do scraping da Estante Virtual

### Entendimento

- A Estante Virtual é uma das três plataformas previstas e já existe como `Plataforma.ESTANTE_VIRTUAL` na configuração.
- O novo coletor deve ficar separado em `scrapers/` e seguir o contrato comum de `Coletor` e `ResultadoColeta`.
- Para cada link configurado da Estante Virtual, deve tentar obter o preço e metadados disponíveis, como título e capa, e representar falhas sem interromper a coleta dos outros links.
- Em links da Estante Virtual, `valor_sem_frete` representa o preço do livro antes do frete. O preço comparado entre plataformas é `valor_sem_frete + frete`, usando frete presumido de R$ 16,00, exceto quando a página indicar claramente frete grátis, caso em que o frete é R$ 0,00.
- Campos específicos de plataforma ficam em `extras`, um objeto opcional e genérico por link no `consolidado.json`. Na Estante Virtual, registrar ali `valor_sem_frete` e, quando útil, o valor de frete aplicado e se ele foi presumido. A ausência de `extras` é válida para links sem dados adicionais.
- Os seletores e a forma de identificar preço, disponibilidade, título e capa serão definidos após inspecionar páginas reais da Estante Virtual; não se presume que a estrutura seja igual à da Amazon.

### Etapas resumidas

1. Inspecionar páginas reais dos links configurados e identificar estruturas para preço, disponibilidade, título e capa.
2. Estender `ResultadoColeta` com campos opcionais para `extras` e `top_n_resultados`, preservando o resultado único usado por links diretos e consumidores atuais.
3. Implementar `ColetorEstanteVirtual` em módulo próprio, validando que recebe somente links dessa plataforma e retornando o formato comum.
4. Extrair e normalizar `valor_sem_frete`; calcular o preço comparável adicionando R$ 16,00, salvo indicação explícita de frete grátis.
5. Tratar produto indisponível, preço ausente, resposta inesperada e falhas HTTP como resultado de erro por link, sem interromper os demais.
6. Integrar o coletor ao fluxo principal, habilitar links da Estante Virtual na configuração e adaptar persistência e apresentação para os dados opcionais e resultados `top_n`.
7. Validar com páginas representativas os casos de sucesso, frete presumido, frete grátis, indisponibilidade e HTML sem preço, revisando os seletores quando a estrutura da página mudar.

### Campo opcional `extras` nos arquivos

- Em `consolidado.json`, cada item de `produtos[].links[]` pode conter `extras`, um objeto chave/valor para informações adicionais específicas da plataforma. Não repetir em `extras` campos já definidos no formato comum do link, como `preco_atual`, `status`, `titulo` ou `url`.
- Para a Estante Virtual, `extras.valor_sem_frete` guarda o preço extraído do livro antes do frete. O `preco_atual` comum guarda o total comparável: preço do livro mais R$ 16,00 presumidos, ou mais R$ 0,00 se houver indicação explícita de frete grátis. O objeto pode ainda registrar `frete_aplicado` e `frete_presumido`.
- Em `historico.json`, manter os preços registrados como totais comparáveis. Assim, métricas, vencedor e histórico usam a mesma base de comparação entre plataformas.

### Regra para `pesquisa` e `top_n`

- `pesquisa=false` representa um link direto de produto e produz um preço escolhido entre as ofertas daquela página. `pesquisa=true` representa uma página de busca; descartar primeiro cards cujo título contenha, em minúsculas, algum texto de `BLACKLIST_BOOKS`, e então considerar até `top_n` cards restantes com preço.
- Entre esses até `top_n` resultados, ignorar ofertas sem preço válido ou indisponíveis e escolher o menor preço comparável. Para a Estante Virtual, comparar preço do livro mais frete presumido de R$ 16,00, exceto quando houver indicação explícita de frete grátis.
- Salvar os candidatos avaliados em `top_n_resultados`, incluindo preço, URL própria do anúncio e, na Estante, `valor_sem_frete`; marcar o selecionado com `escolhido: true`. O resultado do link guarda o preço do escolhido em `preco_atual` e os dados adicionais em `extras`. No histórico, `url` continua sendo a URL configurada para o link; as URLs dos anúncios ficam nos candidatos.
- Cada `LinkConfig` conta uma única vez nas métricas do produto e gera no máximo um preço para o histórico por link e plataforma. `top_n_resultados` é detalhe dos candidatos daquela coleta; não transforma cada candidato em um link monitorado independente. Se nenhum candidato válido restar, o link fica com erro/sem preço e não gera evento de preço no histórico.
- A configuração de exemplo deve usar URL de busca quando `pesquisa=true`; URLs diretas de produto devem usar `pesquisa=false`.
