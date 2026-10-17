-- R04 收款对象与应付供应商不同（只读 SELECT；参数 :cutoff_start、:cutoff_end）
-- 粒度：逐条能找到应付的截至日已结算 PAY 分摊；主表 payee_supplier_id 与应付 supplier_id 按原字符串精确比较。
-- 不加“净额大于 0”过滤，退款后仍保留已经发生的对象差异事实。
WITH cutoff(cutoff_start, cutoff_end) AS (SELECT :cutoff_start, :cutoff_end),
settled_pay_alloc AS (
    SELECT a.allocation_id, a.payment_id, a.ap_id, a.allocated_amount_cents, p.payee_supplier_id
    FROM allocations AS a
    JOIN payments AS p ON p.payment_id = a.payment_id
    CROSS JOIN cutoff AS c
    WHERE p.transaction_type = 'PAY'
      AND p.settlement_status = 'SETTLED'
      AND p.payment_date >= c.cutoff_start
      AND p.payment_date <= c.cutoff_end
),
settled_refund_alloc AS (
    SELECT r.original_allocation_id, SUM(r.allocated_amount_cents) AS refunded_cents
    FROM allocations AS r
    JOIN payments AS rp ON rp.payment_id = r.payment_id
    CROSS JOIN cutoff AS c
    WHERE rp.transaction_type = 'REFUND'
      AND rp.settlement_status = 'SETTLED'
      AND r.original_allocation_id IS NOT NULL
      AND rp.payment_date >= c.cutoff_start
      AND rp.payment_date <= c.cutoff_end
    GROUP BY r.original_allocation_id
),
base AS (
    SELECT spa.allocation_id, spa.payment_id, spa.ap_id, spa.payee_supplier_id,
           spa.allocated_amount_cents,
           COALESCE(sra.refunded_cents, 0) AS refunded_cents,
           spa.allocated_amount_cents - COALESCE(sra.refunded_cents, 0) AS net_cents
    FROM settled_pay_alloc AS spa
    LEFT JOIN settled_refund_alloc AS sra ON sra.original_allocation_id = spa.allocation_id
)
SELECT b.allocation_id AS allocation_id,
       b.payment_id AS payment_id,
       b.ap_id AS ap_id,
       b.allocated_amount_cents AS allocated_amount,
       b.refunded_cents AS refunded_amount,
       b.net_cents AS net_amount,
       pa.supplier_id AS payable_supplier_id,
       pa.payable_amount_cents AS payable_amount,
       b.payee_supplier_id AS payee_supplier_id
FROM base AS b
JOIN payables AS pa ON pa.ap_id = b.ap_id
WHERE b.payee_supplier_id <> pa.supplier_id
ORDER BY b.allocation_id;
