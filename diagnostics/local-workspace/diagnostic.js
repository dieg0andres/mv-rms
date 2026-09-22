export function classifyNumber(value) {
  if (!Number.isInteger(value)) {
    throw new TypeError("value must be an integer");
  }

  return value % 2 === 0 ? "even" : "odd";
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const sample = [2, 7, 12];
  const result = sample.map((value) => `${value}:${classifyNumber(value)}`);
  console.log(result.join(","));
}
