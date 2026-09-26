const recipes = [
  {
    id: 1,
    title: "Lemon chicken & herby rice",
    note: "A bright, comforting one-pan kind of dinner.",
    time: "30 min",
    type: "High protein",
    color: "peach",
    ingredients: "Chicken, rice, lemon, garlic, olive oil, parsley",
    steps:
      "Sear the chicken in a little oil. Add rinsed rice, garlic, and enough stock for the rice. Cover and simmer until the rice is tender and the chicken is fully cooked. Finish with lemon and parsley.",
  },
  {
    id: 2,
    title: "Roasted broccoli pasta",
    note: "Golden edges, a little parmesan, lots of comfort.",
    time: "25 min",
    type: "Vegetarian",
    color: "sage",
    ingredients: "Broccoli, pasta, parmesan, garlic, olive oil",
    steps:
      "Roast broccoli with olive oil and garlic until tender. Cook pasta and reserve a cup of its water. Toss everything together with parmesan and a splash of pasta water.",
  },
  {
    id: 3,
    title: "Chickpea harvest bowls",
    note: "A colourful bowl that makes the most of your pantry.",
    time: "20 min",
    type: "Plant based",
    color: "ochre",
    ingredients: "Chickpeas, rice, carrots, spinach, lemon, tahini",
    steps:
      "Cook rice and warm the chickpeas. Sauté the carrots and spinach. Add everything to bowls and finish with tahini mixed with lemon juice and water.",
  },
];
function Bowl({ small = false, color = "sage" }) {
  return (
    <div
      className={`bowl-art ${small ? "small" : ""} ${color}`}
      aria-hidden="true"
    >
      <div className="plate">
        <i className="food rice" />
        <i className="food green one" />
        <i className="food green two" />
        <i className="food green three" />
        <i className="food tomato one" />
        <i className="food tomato two" />
        <i className="food lemon" />
        <i className="food protein" />
      </div>
      <span className="herb herb-one" />
      <span className="herb herb-two" />
    </div>
  );
}


export { recipes, Bowl };
