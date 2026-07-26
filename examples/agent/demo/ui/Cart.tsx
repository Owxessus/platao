import * as React from "react";

// A UI that renders fine and has a dead button — Basanos catches what the eye misses.
export function Cart() {
  const removeItem = () => {
    console.log("removed");
  };

  return (
    <div>
      <button onClick={removeItem}>Remove</button>
      {/* DEAD: checkout() is never defined anywhere in scope */}
      <button onClick={checkout}>Checkout</button>
      {/* STUB: exists, but the body does nothing */}
      <button onClick={() => {}}>Apply coupon</button>
    </div>
  );
}
