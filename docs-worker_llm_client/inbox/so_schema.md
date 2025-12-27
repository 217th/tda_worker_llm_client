```json
{
  "timeframe": "1M",
  "symbol": "string",
  "as_of_date": "YYYY-MM-DD",

  "trend": {
    "direction": "bull | bear | sideways",
    "trend_strength": "weak | moderate | strong",
    "phase": "impulse | correction | consolidation",
    "cycle_phase": "string",
    "description": "string"
  },

  "waves": [
    {
      "label": "string",
      "degree": "cycle | primary | intermediate | minor",
      "start_date": "YYYY-MM-DD",
      "start_price": "number",
      "end_date": "YYYY-MM-DD|null",
      "end_price": "number|null",
      "confidence": "High | Medium | Low"
    }
  ],

  "wave_scenarios": [
    {
      "id": "WS1",
      "linked_scenarios": ["S1"], 
      "probability": "High | Medium | Low",
      "description": "string",
      "waves": [
        {
          "label": "string",
          "degree": "cycle | primary | intermediate | minor",
          "start_date": "YYYY-MM-DD",
          "start_price": "number",
          "end_date": "YYYY-MM-DD|null",
          "end_price": "number|null"
        }
      ],
      "quantitative_score": {
        "total_score": 0,
        "normalized_probability": 0.0,
        "method_comment": "string"
      }
    }
  ],

  "patterns": [
    {
      "name": "string",
      "direction": "bullish | bearish | neutral",
      "price_zone": ["number", "number"],
      "description": "string"
    }
  ],

  "key_levels": [
    {
      "type": "support | resistance | vpvr_poc | vpvr_hvn | vpvr_lvn | fib | ma",
      "level": "number",
      "source": "string",
      "strength": "1 | 2 | 3 | null",
      "note": "string"
    }
  ],

  "indicators_summary": {
    "ma": {
      "ma12_vs_ma26": "string",
      "description": "string"
    },
    "bb": {
      "state": "string",
      "description": "string"
    },
    "macd": {
      "state": "string",
      "description": "string"
    },
    "rsi": {
      "value_zone": "string",
      "description": "string"
    },
    "adx": {
      "strength": "string",
      "description": "string"
    }
  },

  "risks_and_limitations": {
    "factors": [
      "string"
    ],
    "sensitivity_comment": "string"
  },

  "scenarios": [
    {
      "id": "S1 | S2 | S3 | ...",
      "name": "string",
      "role": "base | bullish | bearish | other",
      "probability": "High | Medium | Low",
      "direction": "up | down | sideways",
      "time_horizon": "string", 
      "targets": [
        { "type": "primary_target | secondary_target | extension", "level": "number" }
      ],
      "target_zones": [
        ["number", "number"]
      ],
      "invalidation_levels": [
        "number"
      ],
      "probability_comment": "string",
      "rationale": "string",
      "quantitative_score": {
        "total_score": 0,
        "components": {
          "structure": 0,
          "momentum_and_patterns": 0,
          "distance_to_invalidation": 0,
          "volume_and_onchain": 0
        },
        "normalized_probability": 0.0,
        "method_comment": "string"
      }
    }
  ],

  "analysis_confidence": {
    "overall_confidence": 0.0,
    "comment": "string"
  },

  "agent_recommendations": {
    "need_weekly": ["string"],
    "need_daily": ["string"],
    "need_derivatives": ["string"],
    "need_onchain": ["string"]
  },

  "summary_for_next_timeframes": {
    "dominant_scenario_id": "string",
    "one_line": "string",
    "key_points": ["string"],

    "trend": {
      "direction": "bull | bear | sideways",
      "cycle_phase": "string",
      "key_message": "string"
    },
    "key_levels_brief": {
      "supports": ["number"],
      "resistances": ["number"]
    },
    "scenarios_brief": {
      "base": "string",
      "bullish": "string",
      "bearish": "string"
    }
  }
}
```

EXAMPLE:

**Shortened example (main fields):**

```json
{
  "timeframe": "1M",
  "symbol": "BTCUSDT",
  "as_of_date": "2025-12-02",

  "trend": {
    "direction": "bear",
    "trend_strength": "strong",
    "phase": "correction",
    "cycle_phase": "late bull market transitioning into a major correction",
    "description": "A multi‑year bullish impulse appears complete, and a large correction is unfolding after the 120k peak area."
  },

  "waves": [
    {
      "label": "Primary I",
      "degree": "primary",
      "start_date": "2018-12-01",
      "start_price": 3100,
      "end_date": "2021-11-01",
      "end_price": 69000,
      "confidence": "High"
    },
    {
      "label": "Primary III/V or extended V",
      "degree": "primary",
      "start_date": "2022-11-01",
      "start_price": 15500,
      "end_date": "2025-06-01",
      "end_price": 120000,
      "confidence": "Medium"
    },
    {
      "label": "Corrective A",
      "degree": "primary",
      "start_date": "2025-07-01",
      "start_price": 120000,
      "end_date": null,
      "end_price": null,
      "confidence": "Medium"
    }
  ],

  "wave_scenarios": [
    {
      "id": "WS1",
      "linked_scenarios": ["S1"],
      "probability": "High",
      "description": "Base count: a 5‑wave impulse up is complete; the current phase is a large corrective wave A down.",
      "waves": [
        {
          "label": "Primary I",
          "degree": "primary",
          "start_date": "2018-12-01",
          "start_price": 3100,
          "end_date": "2021-11-01",
          "end_price": 69000
        },
        {
          "label": "Primary V",
          "degree": "primary",
          "start_date": "2022-11-01",
          "start_price": 15500,
          "end_date": "2025-06-01",
          "end_price": 120000
        },
        {
          "label": "Corrective A",
          "degree": "primary",
          "start_date": "2025-07-01",
          "start_price": 120000,
          "end_date": null,
          "end_price": null
        }
      ],
      "quantitative_score": {
        "total_score": 82,
        "normalized_probability": 0.7,
        "method_comment": "Wave structure from 2018 low to 2025 peak fits a mature 5‑wave impulse with clear subdivisions; the corrective leg from 120k aligns with both key support zones and indicator reversals, making this count more plausible than an ongoing extended V."
      }
    },
    {
      "id": "WS2",
      "linked_scenarios": ["S3"],
      "probability": "Low",
      "description": "Alternative count: the current structure is a still‑unfinished extended wave V up.",
      "waves": [
        {
          "label": "Alt Primary III",
          "degree": "primary",
          "start_date": "2022-11-01",
          "start_price": 15500,
          "end_date": null,
          "end_price": null
        }
      ],
      "quantitative_score": {
        "total_score": 38,
        "normalized_probability": 0.2,
        "method_comment": "To sustain an extended V, price would need to hold above key supports and quickly reclaim the 120k area with renewed momentum; current bearish MACD/RSI configuration and proximity to invalidation levels argue against this scenario."
      }
    }
  ],

  "patterns": [
    {
      "name": "Blow-off Top / Long Upper Wick",
      "direction": "bearish",
      "price_zone": [115000, 120000],
      "description": "Strong candle with a long upper wick and elevated volume around 120k."
    }
  ],

  "key_levels": [
    {
      "type": "resistance",
      "level": 120000,
      "source": "ATH",
      "strength": 3,
      "note": "Presumed top of the major upward wave."
    },
    {
      "type": "support",
      "level": 80000,
      "source": "MA26",
      "strength": 2,
      "note": "Strong dynamic support at the monthly MA26."
    },
    {
      "type": "support",
      "level": 69000,
      "source": "previous_ATH",
      "strength": 3,
      "note": "Previous ATH; potential area for large buying interest."
    }
  ],

  "indicators_summary": {
    "ma": {
      "ma12_vs_ma26": "ma12_above_ma26_but_turning_down",
      "description": "MA12 is still above MA26 but turning down — early stage of a trend reversal."
    },
    "bb": {
      "state": "reversion_from_upper_band",
      "description": "Price returned back inside the bands after breaking above the upper Bollinger band."
    },
    "macd": {
      "state": "bearish_cross",
      "description": "MACD formed a bearish crossover at historically elevated levels."
    }
  },

  "scenarios": [
    {
      "id": "S1",
      "name": "Deep correction toward the prior ATH zone",
      "role": "base",
      "probability": "High",
      "direction": "down",
      "time_horizon": "6-18m",
      "targets": [
        { "type": "primary_target", "level": 80000 },
        { "type": "secondary_target", "level": 69000 }
      ],
      "target_zones": [
        [78000, 82000],
        [67000, 71000]
      ],
      "invalidation_levels": [125000],
      "probability_comment": "Most typical scenario for the end of a multi‑year BTC cycle.",
      "rationale": "Completion of a 5‑wave impulse, bearish MACD/RSI signals, and BTC’s historical cycle behavior.",
      "quantitative_score": {
        "total_score": 78,
        "components": {
          "structure": 32,
          "momentum_and_patterns": 24,
          "distance_to_invalidation": 14,
          "volume_and_onchain": 8
        },
        "normalized_probability": 0.65,
        "method_comment": "Structure: price rejected from a likely terminal zone near 120k and is gravitating toward major support clusters at 80k and 69k (32/40). Momentum/patterns: MACD bearish cross, RSI rolling over from historically high levels, and a blow‑off candle support the idea of a major correction (24/30). Distance to invalidation: current price trades at a reasonable distance from 125k invalidation, allowing room for correction without immediate failure (14/20). Volume/on‑chain: elevated volumes on the peak and early distribution behavior back the corrective view, but on‑chain data is not fully conclusive (8/10)."
      }
    }
  ],

  "analysis_confidence": {
    "overall_confidence": 0.7,
    "comment": "The corrective interpretation is favored, but upcoming macro events and possible structural regime shifts keep confidence below 0.8."
  },

  "agent_recommendations": {
    "need_weekly": [
      "Check the A/B/C corrective structure on 1W and clarify whether wave A has finished."
    ],
    "need_daily": [
      "Search for local patterns (flag, wedge) on lower timeframes for tactical entries."
    ],
    "need_derivatives": [
      "Check whether funding rates and open interest confirm a redistribution/correction scenario."
    ],
    "need_onchain": []
  },

  "summary_for_next_timeframes": {
    "dominant_scenario_id": "S1",
    "one_line": "Globally, the market has entered a major correction after the 120k peak; the base scenario is a move into the 80k–69k zone over the next 6–18 months.",
    "key_points": [
      "A multi‑year bullish impulse (presumably a 5‑wave structure) appears complete.",
      "A large wave A down is forming on 1M.",
      "Key areas of interest: 80k (MA26), 69k (previous ATH), 65k (VPVR POC).",
      "Continuation of the bull trend above 120k is considered unlikely."
    ],
    "trend": {
      "direction": "bear",
      "cycle_phase": "major correction after a multi‑year bull trend",
      "key_message": "On lower timeframes, the main idea is to look for opportunities to trade with the bearish scenario, not to catch a full bull reversal."
    },
    "key_levels_brief": {
      "supports": [80000, 69000],
      "resistances": [120000]
    },
    "scenarios_brief": {
      "base": "Base scenario: a gradual move toward the 80k–69k zone as part of corrective wave A.",
      "bullish": "Bullish scenario: holding above ~80k and a return to 100k+ with formation of a new high.",
      "bearish": "Bearish scenario: a breakdown below 69k and transition into a deeper cycle‑level correction."
    }
  }
}
```