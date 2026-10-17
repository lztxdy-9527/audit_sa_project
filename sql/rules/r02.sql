-- R02 应付单净付款超额（只读 SELECT；参数 :cutoff_start、:cutoff_end）
-- 粒度：唯一 ap_id（已知应付），跨收款对象汇总已结算付款分摊与有效退款分摊；净额严格大于应付金额才命中。
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
per_payable AS (
    SELECT b.ap_id,
           SUM(b.allocated_amount_cents) AS paid_total,
           SUM(b.refunded_cents) AS refund_total,
           SUM(b.net_cents) AS net_total
    FROM base AS b
    JOIN payables AS pa ON pa.ap_id = b.ap_id
    GROUP BY b.ap_id
)
SELECT pa.ap_id AS ap_id,
       pa.payable_amount_cents AS payable_amount,
       pp.paid_total AS paid_total,
       pp.refund_total AS refund_total,
       pp.net_total AS net_total,
       pp.net_total - pa.payable_amount_cents AS overpayment
FROM per_payable AS pp
JOIN payables AS pa ON pa.ap_id = pp.ap_id
WHERE pp.net_total > pa.payable_amount_cents
ORDER BY pa.ap_id;
