-- TASK-005 开发态 SQLite 结构（demo-schema-1.0）
-- 只用标准化结果中的固定字段；金额一律整数分，不设“元”业务金额列。
-- 表名与列名只来自本文件的白名单，业务值一律参数绑定。

CREATE TABLE suppliers (
    supplier_id   TEXT PRIMARY KEY NOT NULL CHECK (length(supplier_id) > 0),
    supplier_name TEXT NOT NULL CHECK (length(supplier_name) > 0)
);

CREATE TABLE payables (
    ap_id                TEXT PRIMARY KEY NOT NULL CHECK (length(ap_id) > 0),
    ap_number            TEXT NOT NULL CHECK (length(ap_number) > 0),
    supplier_id          TEXT NOT NULL REFERENCES suppliers(supplier_id),
    ap_date              TEXT NOT NULL
        CHECK (ap_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    payable_amount_cents INTEGER NOT NULL
        CHECK (typeof(payable_amount_cents) = 'integer' AND payable_amount_cents > 0),
    currency             TEXT NOT NULL CHECK (currency = 'CNY')
);

CREATE TABLE payments (
    payment_id          TEXT PRIMARY KEY NOT NULL CHECK (length(payment_id) > 0),
    transaction_type    TEXT NOT NULL CHECK (transaction_type IN ('PAY', 'REFUND')),
    original_payment_id TEXT REFERENCES payments(payment_id) DEFERRABLE INITIALLY DEFERRED,
    payee_supplier_id   TEXT NOT NULL REFERENCES suppliers(supplier_id),
    payment_date        TEXT NOT NULL
        CHECK (payment_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    amount_cents        INTEGER NOT NULL
        CHECK (typeof(amount_cents) = 'integer' AND amount_cents > 0),
    currency            TEXT NOT NULL CHECK (currency = 'CNY'),
    settlement_status   TEXT NOT NULL
        CHECK (settlement_status IN ('SETTLED', 'PENDING', 'FAILED', 'VOIDED')),
    bank_reference      TEXT,
    CHECK (
        (transaction_type = 'PAY' AND original_payment_id IS NULL)
        OR (transaction_type = 'REFUND' AND original_payment_id IS NOT NULL)
    ),
    CHECK (
        (settlement_status = 'SETTLED' AND bank_reference IS NOT NULL AND length(bank_reference) > 0)
        OR (settlement_status <> 'SETTLED')
    )
);

-- 已结算事件的银行流水标识唯一（非结算允许为空）
CREATE UNIQUE INDEX payments_settled_bank_reference_unique
    ON payments(bank_reference) WHERE settlement_status = 'SETTLED';

CREATE TABLE allocations (
    allocation_id          TEXT PRIMARY KEY NOT NULL CHECK (length(allocation_id) > 0),
    payment_id             TEXT NOT NULL REFERENCES payments(payment_id),
    -- ap_id 故意不设外键：允许 NULL（未指定对象）与台账外文本，均按原值保留
    ap_id                  TEXT CHECK (ap_id IS NULL OR length(ap_id) > 0),
    allocated_amount_cents INTEGER NOT NULL
        CHECK (typeof(allocated_amount_cents) = 'integer' AND allocated_amount_cents > 0),
    original_allocation_id TEXT REFERENCES allocations(allocation_id) DEFERRABLE INITIALLY DEFERRED
);

-- 同一资金事件对同一应付对象只能有一条分摊；ap_id 为 NULL 的组合单独用部分唯一索引约束
CREATE UNIQUE INDEX allocations_payment_ap_unique
    ON allocations(payment_id, ap_id) WHERE ap_id IS NOT NULL;
CREATE UNIQUE INDEX allocations_payment_null_ap_unique
    ON allocations(payment_id) WHERE ap_id IS NULL;

-- 每条业务记录一条来源；以表名 + 业务 ID 唯一关联，不同表的同名 ID 不会混为一条
CREATE TABLE source_records (
    table_name      TEXT NOT NULL
        CHECK (table_name IN ('suppliers', 'payables', 'payments', 'allocations')),
    record_id       TEXT NOT NULL CHECK (length(record_id) > 0),
    workbook_sha256 TEXT NOT NULL CHECK (length(workbook_sha256) = 64),
    sheet           TEXT NOT NULL,
    excel_row       INTEGER NOT NULL
        CHECK (typeof(excel_row) = 'integer' AND excel_row >= 2),
    cells_json      TEXT NOT NULL,
    PRIMARY KEY (table_name, record_id)
);

-- 本次装载的元数据（键值对，全部来自固定白名单）
CREATE TABLE run_metadata (
    metadata_key   TEXT PRIMARY KEY NOT NULL CHECK (length(metadata_key) > 0),
    metadata_value TEXT NOT NULL
);
