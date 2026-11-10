# API samples (generated)

Captured by `scripts/capture_api_samples.py` from a real server on a throwaway database seeded with
`seed_demo`. Everything is fictional. CSRF tokens and scan proofs are redacted; long lists are trimmed.
The contract and error codes are described in [API.md](API.md).

### Health

`GET /api/v1/health/` — as **anonymous**

Response: **200**
```json
{
  "status": "ok",
  "database": "ok"
}
```

### CSRF bootstrap

`GET /api/v1/auth/csrf/` — as **anonymous**

Response: **200**
```json
{
  "csrf_token": "<redacted>"
}
```

### Login without X-CSRFToken is rejected

`POST /api/v1/auth/login/` — as **anonymous**

Request:
```json
{
  "username": "demo_ayesha",
  "password": "RozgarDemo#2026"
}
```

Response: **403**
```json
{
  "detail": "CSRF verification failed. Fetch /api/v1/auth/csrf/ and send X-CSRFToken.",
  "code": "csrf_failed"
}
```

### Catalog: trades

`GET /api/v1/catalog/trades/` — as **anonymous**

Response: **200**
```json
[
  {
    "id": 1,
    "slug": "plumbing",
    "name_en": "Plumbing",
    "name_ur": "پلمبنگ",
    "icon_key": "droplet"
  },
  {
    "id": 2,
    "slug": "electrical",
    "name_en": "Electrical",
    "name_ur": "بجلی کا کام",
    "icon_key": "zap"
  },
  {
    "id": 3,
    "slug": "ac-repair",
    "name_en": "AC Repair",
    "name_ur": "اے سی مرمت",
    "icon_key": "snowflake"
  },
  "... 1 more"
]
```

### Catalog: specialties of one trade

`GET /api/v1/catalog/trades/2/specialties/` — as **anonymous**

Response: **200**
```json
[
  {
    "id": 5,
    "trade": 2,
    "slug": "wiring",
    "name_en": "Wiring",
    "name_ur": "وائرنگ"
  },
  {
    "id": 6,
    "trade": 2,
    "slug": "fan-installation",
    "name_en": "Fan installation",
    "name_ur": "پنکھا لگانا"
  },
  {
    "id": 7,
    "trade": 2,
    "slug": "switchboard-repair",
    "name_en": "Switchboard repair",
    "name_ur": "سوئچ بورڈ کی مرمت"
  },
  "... 1 more"
]
```

### Catalog: service areas

`GET /api/v1/catalog/service-areas/` — as **anonymous**

Response: **200**
```json
[
  {
    "id": 1,
    "city": "Islamabad",
    "sector_code": "G-11",
    "name_en": "G-11",
    "name_ur": "جی-11"
  },
  {
    "id": 2,
    "city": "Islamabad",
    "sector_code": "G-13",
    "name_en": "G-13",
    "name_ur": "جی-13"
  },
  {
    "id": 3,
    "city": "Islamabad",
    "sector_code": "I-10",
    "name_en": "I-10",
    "name_ur": "آئی-10"
  },
  "... 3 more"
]
```

### Login (worker)

`POST /api/v1/auth/login/` — as **worker demo_imran** — header `X-CSRFToken`

Request:
```json
{
  "username": "demo_imran",
  "password": "RozgarDemo#2026"
}
```

Response: **200**
```json
{
  "id": 3,
  "username": "demo_imran",
  "role": "worker"
}
```

### Current user

`GET /api/v1/auth/me/` — as **worker demo_imran**

Response: **200**
```json
{
  "id": 3,
  "username": "demo_imran",
  "role": "worker"
}
```

### Worker profile before onboarding

`GET /api/v1/workers/me/` — as **worker demo_imran**

Response: **404**
```json
{
  "detail": "No worker profile yet. Scan your ID card to create one.",
  "code": "profile_not_found"
}
```

### ID scan: unreadable photo (mock fixture `blurry`)

`POST /api/v1/workers/me/scan/` — as **worker demo_imran** — header `X-CSRFToken`

Request:
```json
{
  "image": "<blurry.jpg (image/jpeg, 75 bytes)>"
}
```

Response: **422**
```json
{
  "detail": "No ID number found. Retake the photo in good light with the whole card visible.",
  "code": "id_not_found",
  "retryable": true,
  "mode": "mock"
}
```

### ID scan (mock OCR, fictional card)

`POST /api/v1/workers/me/scan/` — as **worker demo_imran** — header `X-CSRFToken`

Multipart field `image`. `scan_proof` is single-use and expires in 10 minutes.

Request:
```json
{
  "image": "<card.png (image/png, 72 bytes)>"
}
```

Response: **201**
```json
{
  "mode": "mock",
  "simulated": true,
  "identity": {
    "name_en": "Imran Ali",
    "name_ur": "عمران علی",
    "id_masked": "*****-****005-5"
  },
  "scan_proof": "<redacted>",
  "expires_at": "2026-11-10T14:14:48.639449+05:00"
}
```

### Create worker profile with the scan proof

`PUT /api/v1/workers/me/` — as **worker demo_imran** — header `X-CSRFToken`

Request:
```json
{
  "display_name": "Imran Electric",
  "experience_years": 7,
  "trades": [
    2
  ],
  "specialties": [
    5
  ],
  "service_areas": [
    1,
    2
  ],
  "scan_proof": "<redacted>"
}
```

Response: **201**
```json
{
  "id": 3,
  "display_name": "Imran Electric",
  "experience_years": 7,
  "trades": [
    2
  ],
  "specialties": [
    5
  ],
  "service_areas": [
    1,
    2
  ],
  "accepting_jobs": true,
  "is_complete": true,
  "is_available": true,
  "verification": {
    "name": "Imran Ali",
    "id_masked": "*****-****005-5",
    "verified_at": "2026-11-10T14:04:48.706840+05:00",
    "simulated": true
  },
  "created_at": "2026-11-10T14:04:48.708642+05:00",
  "updated_at": "2026-11-10T14:04:48.708647+05:00"
}
```

### Set accepting-jobs preference

`PATCH /api/v1/workers/me/availability/` — as **worker demo_imran** — header `X-CSRFToken`

Request:
```json
{
  "accepting_jobs": true
}
```

Response: **200**
```json
{
  "accepting_jobs": true,
  "is_available": true
}
```

### Register (always a customer)

`POST /api/v1/auth/register/` — as **customer docs_customer** — header `X-CSRFToken`

Request:
```json
{
  "username": "docs_customer_c89510",
  "password": "RozgarDemo#2026"
}
```

Response: **201**
```json
{
  "id": 10,
  "username": "docs_customer_c89510",
  "role": "customer"
}
```

### Discover available workers

`GET /api/v1/workers/?trade=2&service_area=1&specialty=5` — as **customer docs_customer**

Response: **200**
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 5,
      "display_name": "Akram Electric Works",
      "experience_years": 8,
      "trades": [
        2
      ],
      "specialties": [
        5,
        6
      ],
      "service_areas": [
        1,
        2
      ],
      "verified": true,
      "verification_simulated": true,
      "rating": {
        "average": 4.5,
        "count": 2
      },
      "completed_jobs": 2,
      "matches_specialty": true,
      "is_available": true
    },
    {
      "id": 3,
      "display_name": "Imran Electric",
      "experience_years": 7,
      "trades": [
        2
      ],
      "specialties": [
        5
      ],
      "service_areas": [
        1,
        2
      ],
      "verified": true,
      "verification_simulated": true,
      "rating": {
        "average": null,
        "count": 0
      },
      "completed_jobs": 0,
      "matches_specialty": true,
      "is_available": true
    },
    "... 1 more"
  ]
}
```

### Public worker profile

`GET /api/v1/workers/3/` — as **customer docs_customer**

Response: **200**
```json
{
  "id": 3,
  "display_name": "Imran Electric",
  "experience_years": 7,
  "trades": [
    2
  ],
  "specialties": [
    5
  ],
  "service_areas": [
    1,
    2
  ],
  "verified": true,
  "verification_simulated": true,
  "rating": {
    "average": null,
    "count": 0
  },
  "completed_jobs": 0,
  "is_available": true,
  "recent_reviews": []
}
```

### Post a job request with a voice note

`POST /api/v1/job-requests/` — as **customer docs_customer** — header `X-CSRFToken`

Multipart; JSON also works without `voice_note`. Needs `description` or `voice_note`.

Request:
```json
{
  "trade": 2,
  "service_area": 1,
  "specialty": 5,
  "description": "Switchboard sparks when the fan is switched on",
  "address_details": "House 1, Street 1 (demo)",
  "voice_note": "<recording.webm (audio/webm, 68 bytes)>"
}
```

Response: **201**
```json
{
  "id": 6,
  "status": "OPEN",
  "trade": {
    "id": 2,
    "slug": "electrical",
    "name_en": "Electrical",
    "name_ur": "بجلی کا کام",
    "icon_key": "zap"
  },
  "service_area": {
    "id": 1,
    "city": "Islamabad",
    "sector_code": "G-11",
    "name_en": "G-11",
    "name_ur": "جی-11"
  },
  "specialty": {
    "id": 5,
    "slug": "wiring",
    "name_en": "Wiring",
    "name_ur": "وائرنگ"
  },
  "description": "Switchboard sparks when the fan is switched on",
  "has_voice_note": true,
  "voice_note_url": "/api/v1/job-requests/6/voice-note/",
  "created_at": "2026-11-10T14:04:49.442155+05:00",
  "viewer": "owner",
  "address_details": "House 1, Street 1 (demo)",
  "customer": {
    "id": 10,
    "username": "docs_customer_c89510"
  },
  "booking": null,
  "quotes": [],
  "quote_count": 0
}
```

### My requests (customer)

`GET /api/v1/job-requests/` — as **customer docs_customer**

Response: **200**
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 6,
      "status": "OPEN",
      "trade": {
        "id": 2,
        "slug": "electrical",
        "name_en": "Electrical",
        "name_ur": "بجلی کا کام",
        "icon_key": "zap"
      },
      "service_area": {
        "id": 1,
        "city": "Islamabad",
        "sector_code": "G-11",
        "name_en": "G-11",
        "name_ur": "جی-11"
      },
      "specialty": {
        "id": 5,
        "slug": "wiring",
        "name_en": "Wiring",
        "name_ur": "وائرنگ"
      },
      "description": "Switchboard sparks when the fan is switched on",
      "has_voice_note": true,
      "voice_note_url": "/api/v1/job-requests/6/voice-note/",
      "created_at": "2026-11-10T14:04:49.442155+05:00",
      "viewer": "owner",
      "address_details": "House 1, Street 1 (demo)",
      "customer": {
        "id": 10,
        "username": "docs_customer_c89510"
      },
      "booking": null,
      "quote_count": 0
    }
  ]
}
```

### Job board (worker)

`GET /api/v1/job-board/` — as **worker demo_imran**

Response: **200**
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 6,
      "status": "OPEN",
      "trade": {
        "id": 2,
        "slug": "electrical",
        "name_en": "Electrical",
        "name_ur": "بجلی کا کام",
        "icon_key": "zap"
      },
      "service_area": {
        "id": 1,
        "city": "Islamabad",
        "sector_code": "G-11",
        "name_en": "G-11",
        "name_ur": "جی-11"
      },
      "specialty": {
        "id": 5,
        "slug": "wiring",
        "name_en": "Wiring",
        "name_ur": "وائرنگ"
      },
      "description": "Switchboard sparks when the fan is switched on",
      "has_voice_note": true,
      "voice_note_url": "/api/v1/job-requests/6/voice-note/",
      "created_at": "2026-11-10T14:04:49.442155+05:00",
      "viewer": "eligible_worker",
      "booking": null,
      "my_quote": null
    }
  ],
  "worker_is_available": true
}
```

### Request detail as an eligible worker

`GET /api/v1/job-requests/6/` — as **worker demo_imran**

Response: **200**
```json
{
  "id": 6,
  "status": "OPEN",
  "trade": {
    "id": 2,
    "slug": "electrical",
    "name_en": "Electrical",
    "name_ur": "بجلی کا کام",
    "icon_key": "zap"
  },
  "service_area": {
    "id": 1,
    "city": "Islamabad",
    "sector_code": "G-11",
    "name_en": "G-11",
    "name_ur": "جی-11"
  },
  "specialty": {
    "id": 5,
    "slug": "wiring",
    "name_en": "Wiring",
    "name_ur": "وائرنگ"
  },
  "description": "Switchboard sparks when the fan is switched on",
  "has_voice_note": true,
  "voice_note_url": "/api/v1/job-requests/6/voice-note/",
  "created_at": "2026-11-10T14:04:49.442155+05:00",
  "viewer": "eligible_worker",
  "booking": null,
  "my_quote": null
}
```

### Play the voice note

`GET /api/v1/job-requests/6/voice-note/` — as **worker demo_imran**

Response: **200** `audio/webm`, 68 bytes

### Send a quote

`POST /api/v1/job-requests/6/quotes/` — as **worker demo_imran** — header `X-CSRFToken`

Request:
```json
{
  "amount": "1500",
  "message": "Can come at 5pm"
}
```

Response: **201**
```json
{
  "id": 5,
  "job_request": 6,
  "amount": "1500.00",
  "currency": "PKR",
  "message": "Can come at 5pm",
  "status": "PENDING",
  "created_at": "2026-11-10T14:04:49.696076+05:00"
}
```

### Different second quote is a conflict

`POST /api/v1/job-requests/6/quotes/` — as **worker demo_imran** — header `X-CSRFToken`

Request:
```json
{
  "amount": "1700"
}
```

Response: **409**
```json
{
  "detail": "You already sent a quote for this request.",
  "code": "quote_exists",
  "quote_id": 5
}
```

### Quotes on my request (owner)

`GET /api/v1/job-requests/6/quotes/` — as **customer docs_customer**

Response: **200**
```json
[
  {
    "id": 5,
    "job_request": 6,
    "amount": "1500.00",
    "currency": "PKR",
    "message": "Can come at 5pm",
    "status": "PENDING",
    "created_at": "2026-11-10T14:04:49.696076+05:00",
    "worker": {
      "id": 3,
      "display_name": "Imran Electric",
      "experience_years": 7,
      "trades": [
        2
      ],
      "specialties": [
        5
      ],
      "service_areas": [
        1,
        2
      ],
      "verified": true,
      "verification_simulated": true,
      "rating": {
        "average": null,
        "count": 0
      },
      "completed_jobs": 0,
      "is_available": true
    }
  }
]
```

### Accept a quote

`POST /api/v1/quotes/5/accept/` — as **customer docs_customer** — header `X-CSRFToken`

Response: **201**
```json
{
  "id": 5,
  "status": "BOOKED",
  "amount": "1500.00",
  "currency": "PKR",
  "quote_id": 5,
  "booked_at": "2026-11-10T14:04:49.860003+05:00",
  "checked_in_at": null,
  "completed_at": null,
  "viewer": "customer",
  "actions": [
    "issue_pin",
    "report"
  ],
  "review": null,
  "my_report": null,
  "active_pin": null,
  "worker": {
    "id": 3,
    "display_name": "Imran Electric",
    "experience_years": 7,
    "trades": [
      2
    ],
    "specialties": [
      5
    ],
    "service_areas": [
      1,
      2
    ],
    "verified": true,
    "verification_simulated": true,
    "rating": {
      "average": null,
      "count": 0
    },
    "completed_jobs": 0,
    "is_available": false
  },
  "customer": {
    "id": 10,
    "username": "docs_customer_c89510"
  },
  "job_request": {
    "id": 6,
    "status": "BOOKED",
    "trade": {
      "id": 2,
      "slug": "electrical",
      "name_en": "Electrical",
      "name_ur": "بجلی کا کام",
      "icon_key": "zap"
    },
    "service_area": {
      "id": 1,
      "city": "Islamabad",
      "sector_code": "G-11",
      "name_en": "G-11",
      "name_ur": "جی-11"
    },
    "specialty": {
      "id": 5,
      "slug": "wiring",
      "name_en": "Wiring",
      "name_ur": "وائرنگ"
    },
    "description": "Switchboard sparks when the fan is switched on",
    "has_voice_note": true,
    "voice_note_url": "/api/v1/job-requests/6/voice-note/",
    "created_at": "2026-11-10T14:04:49.442155+05:00",
    "viewer": "owner",
    "address_details": "House 1, Street 1 (demo)",
    "customer": {
      "id": 10,
      "username": "docs_customer_c89510"
    },
    "booking": {
      "id": 5,
      "status": "BOOKED",
      "amount": "1500.00",
      "currency": "PKR"
    },
    "quote_count": 1
  }
}
```

### Worker dashboard while booked

`GET /api/v1/workers/me/dashboard/` — as **worker demo_imran**

Response: **200**
```json
{
  "profile_status": "complete",
  "display_name": "Imran Electric",
  "accepting_jobs": true,
  "is_available": false,
  "active_booking": {
    "id": 5,
    "status": "BOOKED",
    "amount": "1500.00",
    "currency": "PKR",
    "quote_id": 5,
    "booked_at": "2026-11-10T14:04:49.860003+05:00",
    "checked_in_at": null,
    "completed_at": null,
    "viewer": "worker",
    "actions": [
      "check_in",
      "report"
    ],
    "review": null,
    "my_report": null,
    "active_pin": null,
    "worker": {
      "id": 3,
      "display_name": "Imran Electric",
      "experience_years": 7,
      "trades": [
        2
      ],
      "specialties": [
        5
      ],
      "service_areas": [
        1,
        2
      ],
      "verified": true,
      "verification_simulated": true,
      "rating": {
        "average": null,
        "count": 0
      },
      "completed_jobs": 0,
      "is_available": false
    },
    "customer": {
      "id": 10,
      "username": "docs_customer_c89510"
    },
    "job_request": {
      "id": 6,
      "status": "BOOKED",
      "trade": {
        "id": 2,
        "slug": "electrical",
        "name_en": "Electrical",
        "name_ur": "بجلی کا کام",
        "icon_key": "zap"
      },
      "service_area": {
        "id": 1,
        "city": "Islamabad",
        "sector_code": "G-11",
        "name_en": "G-11",
        "name_ur": "جی-11"
      },
      "specialty": {
        "id": 5,
        "slug": "wiring",
        "name_en": "Wiring",
        "name_ur": "وائرنگ"
      },
      "description": "Switchboard sparks when the fan is switched on",
      "has_voice_note": true,
      "voice_note_url": "/api/v1/job-requests/6/voice-note/",
      "created_at": "2026-11-10T14:04:49.442155+05:00",
      "viewer": "assigned_worker",
      "address_details": "House 1, Street 1 (demo)",
      "customer": {
        "id": 10,
        "username": "docs_customer_c89510"
      },
      "booking": {
        "id": 5,
        "status": "BOOKED",
        "amount": "1500.00",
        "currency": "PKR"
      },
      "my_quote": {
        "id": 5,
        "job_request": 6,
        "amount": "1500.00",
        "currency": "PKR",
        "message": "Can come at 5pm",
        "status": "ACCEPTED",
        "created_at": "2026-11-10T14:04:49.696076+05:00"
      }
    }
  },
  "completed_jobs": 0,
  "rating": {
    "average": null,
    "count": 0
  },
  "pending_quotes": 0,
  "open_jobs_matching": 0,
  "recent_jobs": [
    {
      "booking_id": 5,
      "status": "BOOKED",
      "amount": "1500.00",
      "currency": "PKR",
      "trade": 2,
      "service_area": 1,
      "booked_at": "2026-11-10T14:04:49.860003+05:00",
      "completed_at": null,
      "rating": null
    }
  ],
  "links": {
    "bookings": "/api/v1/bookings/",
    "quotes": "/api/v1/quotes/",
    "job_board": "/api/v1/job-board/"
  }
}
```

### Issue arrival PIN (customer)

`POST /api/v1/bookings/5/pin/` — as **customer docs_customer** — header `X-CSRFToken`

The PIN appears only in this response. Sample PIN is from a throwaway database.

Response: **201**
```json
{
  "pin": "674361",
  "expires_at": "2026-11-10T14:19:50.057923+05:00",
  "booking": {
    "id": 5,
    "status": "BOOKED",
    "amount": "1500.00",
    "currency": "PKR",
    "quote_id": 5,
    "booked_at": "2026-11-10T14:04:49.860003+05:00",
    "checked_in_at": null,
    "completed_at": null,
    "viewer": "customer",
    "actions": [
      "issue_pin",
      "report"
    ],
    "review": null,
    "my_report": null,
    "active_pin": {
      "expires_at": "2026-11-10T14:19:50.057923+05:00",
      "attempts_remaining": 5
    },
    "worker": {
      "id": 3,
      "display_name": "Imran Electric",
      "experience_years": 7,
      "trades": [
        2
      ],
      "specialties": [
        5
      ],
      "service_areas": [
        1,
        2
      ],
      "verified": true,
      "verification_simulated": true,
      "rating": {
        "average": null,
        "count": 0
      },
      "completed_jobs": 0,
      "is_available": false
    },
    "customer": {
      "id": 10,
      "username": "docs_customer_c89510"
    },
    "job_request": {
      "id": 6,
      "status": "BOOKED",
      "trade": {
        "id": 2,
        "slug": "electrical",
        "name_en": "Electrical",
        "name_ur": "بجلی کا کام",
        "icon_key": "zap"
      },
      "service_area": {
        "id": 1,
        "city": "Islamabad",
        "sector_code": "G-11",
        "name_en": "G-11",
        "name_ur": "جی-11"
      },
      "specialty": {
        "id": 5,
        "slug": "wiring",
        "name_en": "Wiring",
        "name_ur": "وائرنگ"
      },
      "description": "Switchboard sparks when the fan is switched on",
      "has_voice_note": true,
      "voice_note_url": "/api/v1/job-requests/6/voice-note/",
      "created_at": "2026-11-10T14:04:49.442155+05:00",
      "viewer": "owner",
      "address_details": "House 1, Street 1 (demo)",
      "customer": {
        "id": 10,
        "username": "docs_customer_c89510"
      },
      "booking": {
        "id": 5,
        "status": "BOOKED",
        "amount": "1500.00",
        "currency": "PKR"
      },
      "quote_count": 1
    }
  }
}
```

### Check in with a wrong PIN

`POST /api/v1/bookings/5/check-in/` — as **worker demo_imran** — header `X-CSRFToken`

Request:
```json
{
  "pin": "000000"
}
```

Response: **400**
```json
{
  "detail": "Wrong PIN.",
  "code": "pin_incorrect",
  "attempts_remaining": 4
}
```

### Check in with the PIN (worker)

`POST /api/v1/bookings/5/check-in/` — as **worker demo_imran** — header `X-CSRFToken`

Request:
```json
{
  "pin": "674361"
}
```

Response: **200**
```json
{
  "id": 5,
  "status": "IN_PROGRESS",
  "amount": "1500.00",
  "currency": "PKR",
  "quote_id": 5,
  "booked_at": "2026-11-10T14:04:49.860003+05:00",
  "checked_in_at": "2026-11-10T14:04:50.169058+05:00",
  "completed_at": null,
  "viewer": "worker",
  "actions": [
    "complete",
    "report"
  ],
  "review": null,
  "my_report": null,
  "active_pin": null,
  "worker": {
    "id": 3,
    "display_name": "Imran Electric",
    "experience_years": 7,
    "trades": [
      2
    ],
    "specialties": [
      5
    ],
    "service_areas": [
      1,
      2
    ],
    "verified": true,
    "verification_simulated": true,
    "rating": {
      "average": null,
      "count": 0
    },
    "completed_jobs": 0,
    "is_available": false
  },
  "customer": {
    "id": 10,
    "username": "docs_customer_c89510"
  },
  "job_request": {
    "id": 6,
    "status": "IN_PROGRESS",
    "trade": {
      "id": 2,
      "slug": "electrical",
      "name_en": "Electrical",
      "name_ur": "بجلی کا کام",
      "icon_key": "zap"
    },
    "service_area": {
      "id": 1,
      "city": "Islamabad",
      "sector_code": "G-11",
      "name_en": "G-11",
      "name_ur": "جی-11"
    },
    "specialty": {
      "id": 5,
      "slug": "wiring",
      "name_en": "Wiring",
      "name_ur": "وائرنگ"
    },
    "description": "Switchboard sparks when the fan is switched on",
    "has_voice_note": true,
    "voice_note_url": "/api/v1/job-requests/6/voice-note/",
    "created_at": "2026-11-10T14:04:49.442155+05:00",
    "viewer": "assigned_worker",
    "address_details": "House 1, Street 1 (demo)",
    "customer": {
      "id": 10,
      "username": "docs_customer_c89510"
    },
    "booking": {
      "id": 5,
      "status": "IN_PROGRESS",
      "amount": "1500.00",
      "currency": "PKR"
    },
    "my_quote": {
      "id": 5,
      "job_request": 6,
      "amount": "1500.00",
      "currency": "PKR",
      "message": "Can come at 5pm",
      "status": "ACCEPTED",
      "created_at": "2026-11-10T14:04:49.696076+05:00"
    }
  }
}
```

### Complete the job (worker)

`POST /api/v1/bookings/5/complete/` — as **worker demo_imran** — header `X-CSRFToken`

Response: **200**
```json
{
  "id": 5,
  "status": "COMPLETED",
  "amount": "1500.00",
  "currency": "PKR",
  "quote_id": 5,
  "booked_at": "2026-11-10T14:04:49.860003+05:00",
  "checked_in_at": "2026-11-10T14:04:50.169058+05:00",
  "completed_at": "2026-11-10T14:04:50.274044+05:00",
  "viewer": "worker",
  "actions": [
    "report"
  ],
  "review": null,
  "my_report": null,
  "active_pin": null,
  "worker": {
    "id": 3,
    "display_name": "Imran Electric",
    "experience_years": 7,
    "trades": [
      2
    ],
    "specialties": [
      5
    ],
    "service_areas": [
      1,
      2
    ],
    "verified": true,
    "verification_simulated": true,
    "rating": {
      "average": null,
      "count": 0
    },
    "completed_jobs": 1,
    "is_available": true
  },
  "customer": {
    "id": 10,
    "username": "docs_customer_c89510"
  },
  "job_request": {
    "id": 6,
    "status": "COMPLETED",
    "trade": {
      "id": 2,
      "slug": "electrical",
      "name_en": "Electrical",
      "name_ur": "بجلی کا کام",
      "icon_key": "zap"
    },
    "service_area": {
      "id": 1,
      "city": "Islamabad",
      "sector_code": "G-11",
      "name_en": "G-11",
      "name_ur": "جی-11"
    },
    "specialty": {
      "id": 5,
      "slug": "wiring",
      "name_en": "Wiring",
      "name_ur": "وائرنگ"
    },
    "description": "Switchboard sparks when the fan is switched on",
    "has_voice_note": true,
    "voice_note_url": "/api/v1/job-requests/6/voice-note/",
    "created_at": "2026-11-10T14:04:49.442155+05:00",
    "viewer": "assigned_worker",
    "address_details": "House 1, Street 1 (demo)",
    "customer": {
      "id": 10,
      "username": "docs_customer_c89510"
    },
    "booking": {
      "id": 5,
      "status": "COMPLETED",
      "amount": "1500.00",
      "currency": "PKR"
    },
    "my_quote": {
      "id": 5,
      "job_request": 6,
      "amount": "1500.00",
      "currency": "PKR",
      "message": "Can come at 5pm",
      "status": "ACCEPTED",
      "created_at": "2026-11-10T14:04:49.696076+05:00"
    }
  }
}
```

### Review the completed booking

`POST /api/v1/bookings/5/review/` — as **customer docs_customer** — header `X-CSRFToken`

Request:
```json
{
  "rating": 5,
  "text": "Quick and tidy.",
  "tags": [
    "on_time",
    "clean_work"
  ]
}
```

Response: **201**
```json
{
  "id": 5,
  "rating": 5,
  "text": "Quick and tidy.",
  "tags": [
    "on_time",
    "clean_work"
  ],
  "created_at": "2026-11-10T14:04:50.365324+05:00",
  "booking": 5
}
```

### Report (customer)

`POST /api/v1/bookings/5/reports/` — as **customer docs_customer** — header `X-CSRFToken`

Request:
```json
{
  "reason": "other",
  "details": "Demo report"
}
```

Response: **201**
```json
{
  "id": 1,
  "booking": 5,
  "reason": "other",
  "details": "Demo report",
  "status": "OPEN",
  "created_at": "2026-11-10T14:04:50.396197+05:00"
}
```

### Report (worker)

`POST /api/v1/bookings/5/reports/` — as **worker demo_imran** — header `X-CSRFToken`

Request:
```json
{
  "reason": "payment_dispute"
}
```

Response: **201**
```json
{
  "id": 2,
  "booking": 5,
  "reason": "payment_dispute",
  "details": "",
  "status": "OPEN",
  "created_at": "2026-11-10T14:04:50.434208+05:00"
}
```

### My filed reports

`GET /api/v1/reports/` — as **customer docs_customer**

Response: **200**
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "booking": 5,
      "reason": "other",
      "details": "Demo report",
      "status": "OPEN",
      "created_at": "2026-11-10T14:04:50.396197+05:00"
    }
  ]
}
```

### Booking detail after completion (customer)

`GET /api/v1/bookings/5/` — as **customer docs_customer**

Response: **200**
```json
{
  "id": 5,
  "status": "COMPLETED",
  "amount": "1500.00",
  "currency": "PKR",
  "quote_id": 5,
  "booked_at": "2026-11-10T14:04:49.860003+05:00",
  "checked_in_at": "2026-11-10T14:04:50.169058+05:00",
  "completed_at": "2026-11-10T14:04:50.274044+05:00",
  "viewer": "customer",
  "actions": [],
  "review": {
    "id": 5,
    "rating": 5,
    "text": "Quick and tidy.",
    "tags": [
      "on_time",
      "clean_work"
    ],
    "created_at": "2026-11-10T14:04:50.365324+05:00"
  },
  "my_report": {
    "id": 1,
    "status": "OPEN"
  },
  "active_pin": null,
  "worker": {
    "id": 3,
    "display_name": "Imran Electric",
    "experience_years": 7,
    "trades": [
      2
    ],
    "specialties": [
      5
    ],
    "service_areas": [
      1,
      2
    ],
    "verified": true,
    "verification_simulated": true,
    "rating": {
      "average": 5.0,
      "count": 1
    },
    "completed_jobs": 1,
    "is_available": true
  },
  "customer": {
    "id": 10,
    "username": "docs_customer_c89510"
  },
  "job_request": {
    "id": 6,
    "status": "COMPLETED",
    "trade": {
      "id": 2,
      "slug": "electrical",
      "name_en": "Electrical",
      "name_ur": "بجلی کا کام",
      "icon_key": "zap"
    },
    "service_area": {
      "id": 1,
      "city": "Islamabad",
      "sector_code": "G-11",
      "name_en": "G-11",
      "name_ur": "جی-11"
    },
    "specialty": {
      "id": 5,
      "slug": "wiring",
      "name_en": "Wiring",
      "name_ur": "وائرنگ"
    },
    "description": "Switchboard sparks when the fan is switched on",
    "has_voice_note": true,
    "voice_note_url": "/api/v1/job-requests/6/voice-note/",
    "created_at": "2026-11-10T14:04:49.442155+05:00",
    "viewer": "owner",
    "address_details": "House 1, Street 1 (demo)",
    "customer": {
      "id": 10,
      "username": "docs_customer_c89510"
    },
    "booking": {
      "id": 5,
      "status": "COMPLETED",
      "amount": "1500.00",
      "currency": "PKR"
    },
    "quote_count": 1
  }
}
```

### Review quick tags

`GET /api/v1/reviews/tags/` — as **anonymous**

Response: **200**
```json
[
  {
    "key": "on_time",
    "name_en": "On time",
    "name_ur": "وقت پر آئے"
  },
  {
    "key": "fair_price",
    "name_en": "Fair price",
    "name_ur": "مناسب قیمت"
  },
  {
    "key": "quality_work",
    "name_en": "Quality work",
    "name_ur": "عمدہ کام"
  },
  "... 3 more"
]
```

### Report reasons

`GET /api/v1/reports/reasons/` — as **anonymous**

Response: **200**
```json
[
  {
    "key": "no_show",
    "name_en": "Did not show up",
    "name_ur": "نہیں آئے"
  },
  {
    "key": "unsafe",
    "name_en": "Unsafe behaviour",
    "name_ur": "غیر محفوظ رویہ"
  },
  {
    "key": "harassment",
    "name_en": "Harassment or abuse",
    "name_ur": "بدتمیزی یا ہراسانی"
  },
  "... 4 more"
]
```

### Logout

`POST /api/v1/auth/logout/` — as **worker demo_imran** — header `X-CSRFToken`

Response: **204** `text/html; charset=utf-8`, 0 bytes

### After logout

`GET /api/v1/auth/me/` — as **worker demo_imran**

Response: **403**
```json
{
  "detail": "Authentication credentials were not provided.",
  "code": "not_authenticated"
}
```
