---
title: Preprocessed Tables
impact: HIGH
tags: preprocessed, range-check, bitwise, lookup
---

# Preprocessed Tables

**Impact: HIGH**

Preprocessed tables are constant lookup tables generated before proving. They
enable efficient range checks and bitwise operations.

## Table Types

### Range Check Tables

Verify values are within specific ranges:

```rust
// range_check_20: value in [0, 2^20)
// Table size: 2^20 = 1,048,576 entries
relations! {
    preprocessed {
        range_check_20: value;
    }
}

// range_check_8_8: two 8-bit values
// Table size: 2^16 = 65,536 entries
relations! {
    preprocessed {
        range_check_8_8: limb_0, limb_1;
    }
}

// range_check_m31: M31 field element range
relations! {
    preprocessed {
        range_check_m31: lsl, msl;
    }
}
```

### Bitwise Table

Precomputed bitwise operations:

```rust
// bitwise: a op b = result
// op_id: 0=AND, 1=OR, 2=XOR
relations! {
    preprocessed {
        bitwise: a, b, result, op_id;
    }
}
```

## PreprocessedTable Trait

Each table implements the `PreprocessedTable` trait:

```rust
pub struct Table;

impl PreprocessedTable for Table {
    /// Table size as power of 2
    const LOG_SIZE: u32 = 18;  // 2^18 = 262,144 entries

    /// Compute index into table from column values
    /// SIMD vectorized (16 values per call)
    fn index(values: &[PackedM31]) -> [u32; 16] {
        // Implementation varies by table type
        // Example for range_check_8_8:
        // index = limb_0 + limb_1 * 256
    }

    /// Generate constant table columns
    fn gen_columns() -> ColumnVec<CircleEvaluation<...>> {
        // Generate all possible (value, result) pairs
    }

    /// Define column identifiers
    fn column_ids() -> Vec<PreProcessedColumnId> {
        // Return column IDs for commitment
    }
}
```

## Using Preprocessed Tables

### In AIR (Consume from Table)

```rust
fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
    let cols = ComponentColumns::from_eval(&mut eval);

    // Range check a 20-bit value
    add_to_relation!(eval, self.relations.range_check_20,
        -cols.enabler.clone(),  // Negative = consume
        cols.carry.clone()      // Value to check
    );

    // Range check two 8-bit limbs together
    add_to_relation!(eval, self.relations.range_check_8_8,
        -cols.enabler.clone(),
        cols.limb_0.clone(),
        cols.limb_1.clone()
    );

    // Bitwise operation lookup
    let op_id = E::F::from(BaseField::from_u32_unchecked(OP_XOR));
    add_to_relation!(eval, self.relations.bitwise,
        -cols.enabler.clone(),
        cols.a.clone(),
        cols.b.clone(),
        cols.result.clone(),
        op_id
    );

    eval.finalize_logup_in_pairs();
    eval
}
```

### Register Multiplicities (CRITICAL)

Components using preprocessed tables must register multiplicities:

```rust
pub fn register_multiplicities(
    trace: &[CircleEvaluation<SimdBackend, BaseField, BitReversedOrder>],
    counters: &mut crate::relations::Counters,
) {
    // Always check for empty trace
    if trace.is_empty() {
        return;
    }

    let cols = ComponentColumns::from_iter(trace.iter().map(|eval| &eval.values.data));
    let simd_size = cols.enabler.len();

    // CRITICAL: Use same numerator sign as in gen_interaction_trace!
    // If AIR uses -enabler, use -enabler here too
    let neg_enabler: Vec<PackedM31> = (0..simd_size)
        .map(|i| -cols.enabler[i])
        .collect();

    // Register for range_check_8_8
    counters.range_check_8_8.register_many(
        &neg_enabler,
        &[cols.limb_0, cols.limb_1]
    );

    // Register for bitwise
    counters.bitwise.register_many(
        &neg_enabler,
        &[cols.a, cols.b, cols.result, cols.op_id]
    );
}
```

### Generate Interaction Trace

```rust
pub fn gen_interaction_trace(
    trace: &[CircleEvaluation<...>],
    relations: &Relations,
) -> (ColumnVec<CircleEvaluation<...>>, QM31) {
    if trace.is_empty() {
        return (vec![], QM31::zero());
    }

    let cols = ComponentColumns::from_iter(trace.iter().map(|eval| &eval.values.data));
    let simd_size = cols.enabler.len();
    let log_size = trace[0].domain.log_size();
    let mut interaction_trace = LogupTraceGenerator::new(log_size);

    // Compute numerators (same sign as in register_multiplicities!)
    let neg_enabler: Vec<PackedM31> = (0..simd_size)
        .map(|i| -cols.enabler[i])
        .collect();

    // Range check lookup
    let range_denom = combine!(relations.range_check_8_8,
        [cols.limb_0, cols.limb_1]);
    write_col!(&neg_enabler, &range_denom, interaction_trace);

    // Bitwise lookup
    let bitwise_denom = combine!(relations.bitwise,
        [cols.a, cols.b, cols.result, cols.op_id]);
    write_col!(&neg_enabler, &bitwise_denom, interaction_trace);

    interaction_trace.finalize_last()
}
```

## Multiplicity Tracking

### Counter Types

The `relations!` macro generates counter types:

```rust
// For each preprocessed relation, a Counter is generated
pub struct Counters {
    pub range_check_20: Counter<RangeCheck20>,
    pub range_check_8_8: Counter<RangeCheck8_8>,
    pub bitwise: Counter<Bitwise>,
    // ...
}

impl Counters {
    pub fn new() -> Self {
        Self {
            range_check_20: Counter::new(),
            range_check_8_8: Counter::new(),
            bitwise: Counter::new(),
        }
    }
}
```

### Counter Methods

```rust
impl<T: PreprocessedTable> Counter<T> {
    /// Increment multiplicity for single value
    pub fn increment(&mut self, values: &[M31]) {
        let idx = T::index_single(values);
        self.counts[idx] += 1;
    }

    /// Register many values at once (SIMD)
    pub fn register_many(
        &mut self,
        numerators: &[PackedM31],
        columns: &[&[PackedM31]]
    ) {
        for i in 0..numerators.len() {
            let indices = T::index(&columns.iter()
                .map(|c| c[i])
                .collect::<Vec<_>>());
            for (j, idx) in indices.iter().enumerate() {
                // Numerator determines increment/decrement
                self.counts[*idx as usize] += numerators[i].to_array()[j];
            }
        }
    }
}
```

## Full Lifecycle

1. **Execution**: Runner records operations
2. **Main trace**: Convert to columnar format
3. **Register multiplicities**: Count table accesses
4. **Preprocessed trace**: Generate constant columns + multiplicity columns
5. **Interaction trace**: LogUp fractions for lookups
6. **AIR evaluation**: Verify lookup constraints balance

```rust
// In main prove flow
pub fn gen_trace(mut tracer: Tracer) -> Traces {
    let mut counters = Counters::new();

    // Generate opcode traces
    let opcodes = opcodes::gen_trace(tracer, &mut counters);

    // Register multiplicities for components using preprocessed tables
    memory::witness::register_multiplicities(&memory_trace, &mut counters);
    base_alu_reg::witness::register_multiplicities(&alu_trace, &mut counters);

    // Convert counters to preprocessed traces
    let preprocessed = preprocessed::Traces::from_counters(counters);

    Traces { opcodes, preprocessed, /* ... */ }
}
```

## Common Errors

### Sign Mismatch

**WRONG:**

```rust
// In AIR: negative multiplicity
add_to_relation!(eval, self.relations.range_check_8_8, -enabler, ...);

// In register_multiplicities: positive numerator
let pos_enabler = enabler.clone();  // WRONG SIGN!
counters.range_check_8_8.register_many(&pos_enabler, ...);
```

**CORRECT:**

```rust
// Both use same sign
add_to_relation!(eval, self.relations.range_check_8_8, -enabler, ...);
let neg_enabler = -enabler;
counters.range_check_8_8.register_many(&neg_enabler, ...);
```

### Missing Registration

If a component consumes from a preprocessed table but doesn't call
`register_multiplicities`, the LogUp sum won't balance.

### Wrong Column Order

Fields in `register_many` columns must match relation definition order.
