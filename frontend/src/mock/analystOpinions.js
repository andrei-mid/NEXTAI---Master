// Example AI analyst opinions for mock mode (no server, no LLM key), keyed by CUI. The shape is
// GET /companies/{cui}/analyst-opinion (verifirm/schema/analyst.py, docs/schema/AnalystOpinion.json).
// These are the REAL answers of Qwen2.5-72B-Instruct on the fictional demo companies' dossiers
// (fixtures + their fixture score and signals, 2026-10-29), after the code's citation checks, so
// the screen shows what the model actually says, rejected flags included.
// Real companies (Dedeman) never get one here: no real-company figures in git (CLAUDE.md rule 11).
// `origin: 'example'` is frontend-only.

export const exampleOpinions = {
  "99000017": {
    "origin": "example",
    "cui": "99000017",
    "run_id": "example-99000017",
    "generated_at": "2026-10-28T08:00:00Z",
    "model": "Qwen/Qwen2.5-72B-Instruct",
    "flags": [],
    "rejected": [],
    "opinion_score": 95,
    "explanation": "The financial statements show consistent growth in turnover, net profit, and equity over the years. The company maintains a healthy net margin and low debt-to-turnover ratio. No significant discrepancies or suspicious changes were found in the cross-checks or financial indicators.",
    "disclaimer": "This is my educated opinion, but I am not legally responsible: the analyst must confirm.",
    "official_band": "green",
    "official_score": 100.0
  },
  "99000025": {
    "origin": "example",
    "cui": "99000025",
    "run_id": "example-99000025",
    "generated_at": "2026-10-28T08:00:00Z",
    "model": "Qwen/Qwen2.5-72B-Instruct",
    "flags": [
      {
        "title": "Equity Below Share Capital in 2025",
        "claim": "In 2025, the company's equity was -111,000 RON, which is significantly below the 200 RON share capital.",
        "category": "financial_inconsistency",
        "severity": "high",
        "evidence": [
          {
            "path": "financials.2025.equity",
            "value": "-111000"
          },
          {
            "path": "financials.2025.share_capital",
            "value": "200"
          },
          {
            "path": "signals.FIN-NET-ASSETS-01:946fb6067dae21fe.data.equity",
            "value": "-111000"
          },
          {
            "path": "signals.FIN-NET-ASSETS-01:946fb6067dae21fe.data.share_capital",
            "value": "200"
          }
        ]
      },
      {
        "title": "Administrator Change in 2025",
        "claim": "The administrator changed from Administrator A to Administrator B on 2025-11-02.",
        "category": "suspicious_change",
        "severity": "medium",
        "evidence": [
          {
            "path": "administrators.0.valid_to",
            "value": "2025-11-02"
          },
          {
            "path": "administrators.1.valid_from",
            "value": "2025-11-02"
          },
          {
            "path": "signals.ID-ADMIN-CHANGE-01:d3ec8d35fc9bcfb1.data.previous",
            "value": "Administrator A"
          },
          {
            "path": "signals.ID-ADMIN-CHANGE-01:d3ec8d35fc9bcfb1.data.current",
            "value": "Administrator B"
          },
          {
            "path": "signals.ID-ADMIN-CHANGE-01:d3ec8d35fc9bcfb1.data.changed_on",
            "value": "2025-11-02"
          }
        ]
      },
      {
        "title": "Registered Office Shared by 63 Companies",
        "claim": "The registered office at Str. Exemplului nr. 1, Sector 9, București is shared by 63 companies.",
        "category": "other",
        "severity": "medium",
        "evidence": [
          {
            "path": "signals.ID-SHARED-OFFICE-01:d4ced78be89b57c4.data.address",
            "value": "Str. Exemplului nr. 1, Sector 9, București"
          },
          {
            "path": "signals.ID-SHARED-OFFICE-01:d4ced78be89b57c4.data.n_companies",
            "value": "63"
          }
        ]
      },
      {
        "title": "Sole Shareholder Inactive Since 2023-09-01",
        "claim": "The sole shareholder, Calbrona Holding Fictiv SRL, has been ANAF inactive since 2023-09-01.",
        "category": "other",
        "severity": "medium",
        "evidence": [
          {
            "path": "signals.NET-PARTNER-INACTIVE-01:afa50b8bfa5181b8.data.partner_cui",
            "value": "99000090"
          },
          {
            "path": "signals.NET-PARTNER-INACTIVE-01:afa50b8bfa5181b8.data.inactive_since",
            "value": "2023-09-01"
          }
        ]
      }
    ],
    "rejected": [
      {
        "flag": {
          "title": "Turnover per Employee in 2025 is Extremely High",
          "claim": "In 2025, the company reported a turnover of 18,600,000 RON with only 2 employees, resulting in a turnover per employee of 9,300,000 RON, which is 20.7 times higher than the estimated CAEN 49 average of 450,000 RON per employee.",
          "category": "financial_inconsistency",
          "severity": "high",
          "evidence": [
            {
              "path": "financials.2025.turnover",
              "value": "18600000"
            },
            {
              "path": "financials.2025.employees",
              "value": "2"
            },
            {
              "path": "indicators.2025.turnover_per_employee",
              "value": "9300000"
            },
            {
              "path": "signals.FIN-HEADCOUNT-01:26df309eeea01bf2.data.caen_avg_turnover_per_employee",
              "value": "450000"
            },
            {
              "path": "signals.FIN-HEADCOUNT-01:26df309eeea01bf2.data.ratio_to_avg",
              "value": "20.7"
            }
          ]
        },
        "reason": "states 49, which is not in its evidence"
      },
      {
        "flag": {
          "title": "Discrepancy in 2025 Financial Figures",
          "claim": "The submitted 2025 financial figures differ from ANAF records: turnover 25,400,000 RON vs 18,600,000 RON, net result +1,200,000 RON vs -350,000 RON, and employees 14 vs 2.",
          "category": "cross_source_mismatch",
          "severity": "high",
          "evidence": [
            {
              "path": "signals.TAX-DECLARED-GAP-01:f09bcd9990a5267f.data.submitted.turnover",
              "value": "25400000"
            },
            {
              "path": "signals.TAX-DECLARED-GAP-01:f09bcd9990a5267f.data.official.turnover",
              "value": "18600000"
            },
            {
              "path": "signals.TAX-DECLARED-GAP-01:f09bcd9990a5267f.data.submitted.net_profit",
              "value": "1200000"
            },
            {
              "path": "signals.TAX-DECLARED-GAP-01:f09bcd9990a5267f.data.official.net_profit",
              "value": "-350000"
            },
            {
              "path": "signals.TAX-DECLARED-GAP-01:f09bcd9990a5267f.data.submitted.employees",
              "value": "14"
            },
            {
              "path": "signals.TAX-DECLARED-GAP-01:f09bcd9990a5267f.data.official.employees",
              "value": "2"
            }
          ]
        },
        "reason": "states 2025, 2025, which is not in its evidence"
      },
      {
        "flag": {
          "title": "Circular Invoicing in 2025",
          "claim": "In 2025, invoices of 2,100,000 RON formed a cycle: Zephyria -> Mirelda -> Kestrel -> Zephyria.",
          "category": "other",
          "severity": "high",
          "evidence": [
            {
              "path": "signals.NET-CIRCULAR-INVOICE-01:d2b11638d32fcf92.data.total_ron",
              "value": "2100000"
            },
            {
              "path": "signals.NET-CIRCULAR-INVOICE-01:d2b11638d32fcf92.data.cycle",
              "value": "[\"99000025\", \"99000082\", \"99000041\", \"99000025\"]"
            }
          ]
        },
        "reason": "evidence path 'signals.NET-CIRCULAR-INVOICE-01:d2b11638d32fcf92.data.cycle' is a section, not a value"
      },
      {
        "flag": {
          "title": "No Online Presence Despite High Turnover",
          "claim": "Despite reporting a turnover of 18,600,000 RON in 2025, the company has no website, job postings, SEAP contracts, or EU-funded projects.",
          "category": "data_gap",
          "severity": "medium",
          "evidence": [
            {
              "path": "signals.PRE-NO-FOOTPRINT-01:10ef127cd631f2e3.data.turnover",
              "value": "18600000"
            },
            {
              "path": "signals.PRE-NO-FOOTPRINT-01:10ef127cd631f2e3.data.website",
              "value": "false"
            },
            {
              "path": "signals.PRE-NO-FOOTPRINT-01:10ef127cd631f2e3.data.jobs",
              "value": "0"
            },
            {
              "path": "signals.PRE-NO-FOOTPRINT-01:10ef127cd631f2e3.data.seap",
              "value": "0"
            },
            {
              "path": "signals.PRE-NO-FOOTPRINT-01:10ef127cd631f2e3.data.kohesio",
              "value": "0"
            }
          ]
        },
        "reason": "states 2025, which is not in its evidence"
      }
    ],
    "opinion_score": 30,
    "explanation": "The company shows significant financial inconsistencies, including extremely high turnover per employee and negative equity. There are also discrepancies in financial figures, circular invoicing, and a lack of online presence despite high turnover. These issues raise substantial concerns about the company's financial health and operational transparency.",
    "disclaimer": "This is my educated opinion, but I am not legally responsible: the analyst must confirm.",
    "official_band": "red",
    "official_score": 65.3
  },
  "99000033": {
    "origin": "example",
    "cui": "99000033",
    "run_id": "example-99000033",
    "generated_at": "2026-10-28T08:00:00Z",
    "model": "Qwen/Qwen2.5-72B-Instruct",
    "flags": [
      {
        "title": "Increasing Debts and Decreasing Equity",
        "claim": "Total debts increased from 9,800,000 RON in 2021 to 19,400,000 RON in 2025, while equity decreased from 6,500,000 RON to 2,500,000 RON over the same period.",
        "category": "financial_inconsistency",
        "severity": "high",
        "evidence": [
          {
            "path": "financials.2021.total_debts",
            "value": "9800000"
          },
          {
            "path": "financials.2025.total_debts",
            "value": "19400000"
          },
          {
            "path": "financials.2021.equity",
            "value": "6500000"
          },
          {
            "path": "financials.2025.equity",
            "value": "2500000"
          }
        ]
      },
      {
        "title": "Consistent Net Losses Over Three Years",
        "claim": "The company reported net losses in three consecutive years: 2023 (-400,000 RON), 2024 (-1,900,000 RON), and 2025 (-2,600,000 RON).",
        "category": "financial_inconsistency",
        "severity": "high",
        "evidence": [
          {
            "path": "financials.2023.net_profit",
            "value": "-400000"
          },
          {
            "path": "financials.2024.net_profit",
            "value": "-1900000"
          },
          {
            "path": "financials.2025.net_profit",
            "value": "-2600000"
          }
        ]
      },
      {
        "title": "Discrepancy Between Declared and Official Net Profit",
        "claim": "The company submitted a net profit of 300,000 RON for 2025, but ANAF shows a net loss of 2,600,000 RON.",
        "category": "cross_source_mismatch",
        "severity": "high",
        "evidence": [
          {
            "path": "signals.TAX-DECLARED-GAP-01:19b98b18d1349ce9.claim",
            "value": "Submitted 2025 net result is +300,000 RON while ANAF shows -2,600,000 RON."
          }
        ]
      },
      {
        "title": "VAT Registration Cancellation and Re-registration",
        "claim": "VAT registration was cancelled on 2025-02-01 and re-registered on 2025-09-15.",
        "category": "suspicious_change",
        "severity": "medium",
        "evidence": [
          {
            "path": "signals.TAX-VAT-CANCELLED-01:047e4a12e66d563c.claim",
            "value": "VAT registration was cancelled on 2025-02-01 and re-registered on 2025-09-15."
          }
        ]
      },
      {
        "title": "Arrears on Tax Payments",
        "claim": "The company is on the Q2 2026 ANAF arrears list with 412,560 RON principal and 96,300 RON accessories.",
        "category": "financial_inconsistency",
        "severity": "high",
        "evidence": [
          {
            "path": "signals.TAX-ARREARS-01:239efc600595d3b9.claim",
            "value": "The company is on the Q2 2026 ANAF arrears list with 412,560 RON principal and 96,300 RON accessories."
          }
        ]
      },
      {
        "title": "Insolvency Request by ANAF",
        "claim": "ANAF requested the opening of insolvency in case 9101/99/2026, with the next hearing on 2026-11-20.",
        "category": "suspicious_change",
        "severity": "high",
        "evidence": [
          {
            "path": "signals.LIT-INSOLVENCY-REQUEST-01:7ce34e153e38c390.claim",
            "value": "ANAF requested the opening of insolvency in case 9101/99/2026 (first instance, next hearing 2026-11-20). The procedure is not opened."
          }
        ]
      },
      {
        "title": "Supplier Claiming Unpaid Invoices",
        "claim": "A supplier claims 1,800,000 RON in case 9102/99/2025, now on appeal.",
        "category": "financial_inconsistency",
        "severity": "high",
        "evidence": [
          {
            "path": "signals.LIT-MATERIAL-CLAIM-01:34f63dd7c9b34fe6.claim",
            "value": "A supplier claims 1,800,000 RON in case 9102/99/2025, now on appeal."
          }
        ]
      },
      {
        "title": "Inactive Shareholder",
        "claim": "The sole shareholder Calbrona Holding Fictiv SRL is ANAF inactive since 2023-09-01.",
        "category": "suspicious_change",
        "severity": "medium",
        "evidence": [
          {
            "path": "signals.NET-PARTNER-INACTIVE-01:e3d7e869f215048a.claim",
            "value": "The sole shareholder Calbrona Holding Fictiv SRL is ANAF inactive since 2023-09-01."
          }
        ]
      }
    ],
    "rejected": [
      {
        "flag": {
          "title": "Significant Turnover Decline Over Three Years",
          "claim": "Turnover declined from 32,000,000 RON in 2021 to 15,200,000 RON in 2025, a decrease of 52.5%.",
          "category": "financial_inconsistency",
          "severity": "high",
          "evidence": [
            {
              "path": "financials.2021.turnover",
              "value": "32000000"
            },
            {
              "path": "financials.2025.turnover",
              "value": "15200000"
            },
            {
              "path": "indicators.2025.turnover_growth_pct",
              "value": "-30.0"
            }
          ]
        },
        "reason": "states 52.5, which is not in its evidence"
      }
    ],
    "opinion_score": 30,
    "explanation": "There are also discrepancies in reported financials, tax arrears, and legal issues such as insolvency requests and supplier claims. These factors indicate high risk.",
    "disclaimer": "This is my educated opinion, but I am not legally responsible: the analyst must confirm.",
    "official_band": "red",
    "official_score": 67.8
  }
};
