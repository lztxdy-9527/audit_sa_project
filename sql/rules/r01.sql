-- R01 现存重复足额付款（只读 SELECT；参数 :cutoff_start、:cutoff_end；无硬编码案例 ID／金额／种子）
-- 粒度：(ap_id, payee_supplier_id) 分组内，逐 payment_id 求该应付的退款后净额，净额精确等于应付金额的不同付款至少两笔时成一条线索。
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
),
per_payment AS (
    SELECT b.ap_id, b.payee_supplier_id, b.payment_id, SUM(b.net_cents) AS net_per_payment
    FROM base AS b
    JOIN payables AS pa ON pa.ap_id = b.ap_id
    GROUP BY b.ap_id, b.payee_supplier_id, b.payment_id
),
qualifying AS (
    SELECT pp.ap_id, pp.payee_supplier_id, pp.payment_id, pp.net_per_payment
    FROM per_payment AS pp
    JOIN payables AS pa ON pa.ap_id = pp.ap_id
    WHERE pp.net_per_payment = pa.payable_amount_cents
),
grouped AS (
    SELECT q.ap_id, q.payee_supplier_id, COUNT(*) AS qualifier_count,
           SUM(q.net_per_payment) AS net_total
    FROM qualifying AS q
    GROUP BY q.ap_id, q.payee_supplier_id
    HAVING COUNT(*) >= 2
)
SELECT g.ap_id AS ap_id,
       g.payee_supplier_id AS payee_supplier_id,
       g.qualifier_count AS qualifier_count,
       g.net_total AS net_total,
       pa.payable_amount_cents AS payable_amount,
       q.payment_id AS payment_id,
       q.net_per_payment AS net_per_payment
FROM grouped AS g
JOIN payables AS pa ON pa.ap_id = g.ap_id
JOIN qualifying AS q ON q.ap_id = g.ap_id AND q.payee_supplier_id = g.payee_supplier_id
ORDER BY g.ap_id, g.payee_supplier_id, q.payment_id;
