---
title: Constraint Patterns
impact: HIGH
tags: constraints, air, polynomial, arithmetic
---

# Constraint Patterns

**Impact: HIGH**

Common constraint patterns for Stwo AIR development.

## Basic Constraint Structure

### Adding Constraints

```rust
fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
    // Simple equality constraint: a = b
    eval.add_constraint(cols.a.clone() - cols.b.clone());

    // Conditional constraint: if enabled, a = b
    eval.add_constraint(
        cols.enabler.clone() * (cols.a.clone() - cols.b.clone())
    );

    eval
}
```

### Constraint Degree

Maximum polynomial degree is `3`:

```rust
// Degree 2: enabler * (a - b)
eval.add_constraint(enabler.clone() * (a - b));

// Degree 3: enabler * a * b (careful!)
eval.add_constraint(enabler.clone() * a.clone() * b.clone());

// Degree 4+: May exceed limit - split into multiple constraints
// WRONG if log_size = 2:
eval.add_constraint(a * b * c * d);  // Degree 4 > 3
```

## Boolean Constraints

### Single Boolean

```rust
// Constrain x to be 0 or 1
eval.add_constraint(cols.x.clone() * (E::F::one() - cols.x.clone()));
```

### Mutual Exclusion

```rust
// At most one of flag_a, flag_b, flag_c is 1
let sum = cols.flag_a.clone() + cols.flag_b.clone() + cols.flag_c.clone();
eval.add_constraint(sum.clone() * (E::F::one() - sum.clone()));

// Each flag is boolean
eval.add_constraint(cols.flag_a.clone() * (E::F::one() - cols.flag_a.clone()));
eval.add_constraint(cols.flag_b.clone() * (E::F::one() - cols.flag_b.clone()));
eval.add_constraint(cols.flag_c.clone() * (E::F::one() - cols.flag_c.clone()));
```

### Exactly One (Selector)

```rust
// Exactly one of flag_a, flag_b, flag_c is 1
let sum = cols.flag_a.clone() + cols.flag_b.clone() + cols.flag_c.clone();
eval.add_constraint(sum - E::F::one());  // sum = 1

// Plus boolean constraints for each flag
```

## Arithmetic Constraints

### Limb Decomposition

```rust
// 32-bit value from 4 8-bit limbs
let shift_8 = E::F::from(BaseField::from_u32_unchecked(1 << 8));
let shift_16 = E::F::from(BaseField::from_u32_unchecked(1 << 16));
let shift_24 = E::F::from(BaseField::from_u32_unchecked(1 << 24));

let value = cols.limb_0.clone()
    + cols.limb_1.clone() * shift_8.clone()
    + cols.limb_2.clone() * shift_16.clone()
    + cols.limb_3.clone() * shift_24.clone();

// Constrain decomposition
eval.add_constraint(cols.full_value.clone() - value);
```

### Addition with Carry

```rust
// a + b = sum + carry * 2^32
let two_32 = E::F::from(BaseField::from_u32_unchecked(1 << 16))
    * E::F::from(BaseField::from_u32_unchecked(1 << 16));

eval.add_constraint(
    cols.a.clone() + cols.b.clone()
    - cols.sum.clone()
    - cols.carry.clone() * two_32
);

// Carry must be boolean (0 or 1)
eval.add_constraint(cols.carry.clone() * (E::F::one() - cols.carry.clone()));
```

### Multiplication

```rust
// For 32x32 -> 64 bit multiplication: a * b = lo + hi * 2^32
// Split into limbs to avoid overflow
let a_lo = cols.a_limb_0.clone() + cols.a_limb_1.clone() * shift_8;
let a_hi = cols.a_limb_2.clone() + cols.a_limb_3.clone() * shift_8;
// Similar for b, result

// Constrain: a * b = result (modular)
// This requires careful handling of carries
```

## Conditional Logic

### If-Then-Else

```rust
// result = if flag then a else b
// Equivalent: result = flag * a + (1 - flag) * b
eval.add_constraint(
    cols.result.clone()
    - cols.flag.clone() * cols.a.clone()
    - (E::F::one() - cols.flag.clone()) * cols.b.clone()
);
```

### Switch Statement

```rust
// result =
//   if flag_a then val_a
//   else if flag_b then val_b
//   else val_c

// Assuming exactly one flag is set:
eval.add_constraint(
    cols.result.clone()
    - cols.flag_a.clone() * cols.val_a.clone()
    - cols.flag_b.clone() * cols.val_b.clone()
    - cols.flag_c.clone() * cols.val_c.clone()
);
```

## Range Checks via LogUp

### Range Check Pattern

```rust
// Check that value is in [0, 2^20) via preprocessed table
add_to_relation!(eval, self.relations.range_check_20,
    -cols.enabler.clone(),  // Consume from range table
    cols.value.clone()
);

// The preprocessed table contains all values 0..2^20
// If value is out of range, lookup will fail
```

### Byte Range Check

```rust
// Check each limb is a valid byte
for limb in [&cols.limb_0, &cols.limb_1, &cols.limb_2, &cols.limb_3] {
    add_to_relation!(eval, self.relations.range_check_8,
        -cols.enabler.clone(),
        limb.clone()
    );
}
```

## Memory Access Patterns

### Read Pattern

```rust
// Read from memory at address
add_to_relation!(eval, self.relations.memory_access,
    -cols.enabler.clone(),  // Consume (read)
    E::F::from(BaseField::from_u32_unchecked(MEMORY_AS)),  // Address space
    cols.addr.clone(),
    cols.clk.clone(),
    cols.value_limb_0.clone(),
    cols.value_limb_1.clone(),
    cols.value_limb_2.clone(),
    cols.value_limb_3.clone()
);
```

### Write Pattern

```rust
// Write to memory - same structure, different address space or timing
add_to_relation!(eval, self.relations.memory_access,
    cols.enabler.clone(),  // Emit (write produces new state)
    E::F::from(BaseField::from_u32_unchecked(MEMORY_AS)),
    cols.addr.clone(),
    cols.clk.clone() + E::F::one(),  // Next clock
    cols.new_value_limb_0.clone(),
    cols.new_value_limb_1.clone(),
    cols.new_value_limb_2.clone(),
    cols.new_value_limb_3.clone()
);
```

## Opcode-Specific Patterns

### Immediate Value Handling

```rust
// Sign-extend 12-bit immediate to 32 bits
// imm[11] is sign bit
let sign_bit = cols.imm_11.clone();
let sign_ext = sign_bit.clone() * E::F::from(BaseField::from_u32_unchecked(0xFFFFF000));

let extended_imm = cols.imm_low.clone() + sign_ext;
```

### Branch Condition

```rust
// Branch if equal: branch when rs1 == rs2
// Use subtraction and check if zero
let diff = cols.rs1_value.clone() - cols.rs2_value.clone();

// is_zero flag must be 1 iff diff == 0
// Constrain: diff * is_zero = 0 (if zero, is_zero can be 1)
// Constrain: diff * inv = 1 - is_zero (if non-zero, must have inverse)
eval.add_constraint(cols.diff.clone() * cols.is_zero.clone());
eval.add_constraint(
    cols.diff.clone() * cols.inv.clone()
    - (E::F::one() - cols.is_zero.clone())
);
```

## Documentation Pattern

Always reference the specification:

```rust
fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
    // =============================================
    // Section 3.2: ADD Instruction
    // =============================================
    // rd = rs1 + rs2
    //
    // Variables:
    //   - enabler: instruction is ADD
    //   - rs1_val, rs2_val: source register values
    //   - rd_val: destination register value
    //   - carry: overflow indicator

    let cols = ComponentColumns::from_eval(&mut eval);

    // Constraint 3.2.1: Result correctness
    // rd_val = (rs1_val + rs2_val) mod 2^32
    eval.add_constraint(
        cols.enabler.clone() * (
            cols.rd_val.clone()
            - cols.rs1_val.clone()
            - cols.rs2_val.clone()
            + cols.carry.clone() * two_32
        )
    );

    // Constraint 3.2.2: Carry range check
    // carry ∈ {0, 1}
    eval.add_constraint(
        cols.enabler.clone() * cols.carry.clone()
        * (E::F::one() - cols.carry.clone())
    );

    eval
}
```
