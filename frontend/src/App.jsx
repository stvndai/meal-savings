import { useEffect, useRef, useState } from 'react';
import { ArrowRight, ClipboardPaste, ImagePlus, LoaderCircle, Plus, Sprout, Upload, X } from 'lucide-react';
import { Bowl } from './recipes.jsx';
import { extractAndMatch, recipeUrl } from './api.js';

const MAX_IMAGES = 10;
const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

export default function App() {
  const [images, setImages] = useState([]);
  const [notice, setNotice] = useState('');
  const [dragging, setDragging] = useState(false);
  const [showRecipes, setShowRecipes] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const busyRef = useRef(false);
  const [selected, setSelected] = useState(null);
  const inputRef = useRef(null);
  const imageRef = useRef([]);
  const dialogRef = useRef(null);
  const resultsRef = useRef(null);

  useEffect(() => () => imageRef.current.forEach(image => URL.revokeObjectURL(image.url)), []);
  useEffect(() => {
    if (selected) dialogRef.current?.showModal();
    else dialogRef.current?.close();
  }, [selected]);
  useEffect(() => {
    if (showRecipes) resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [showRecipes]);

  function addImages(files) {
    if (busyRef.current) return;
    setError('');
    const incoming = Array.from(files);
    const accepted = incoming.filter(file => IMAGE_TYPES.includes(file.type) && file.size > 0 && file.size <= 10 * 1024 * 1024);
    const remaining = MAX_IMAGES - imageRef.current.length;
    const additions = accepted.slice(0, remaining).map(file => ({ id: crypto.randomUUID(), file, url: URL.createObjectURL(file) }));
    if (additions.length) {
      imageRef.current = [...imageRef.current, ...additions];
      setImages(imageRef.current);
      setShowRecipes(false);
    }
    const warnings = [];
    if (accepted.length !== incoming.length) warnings.push('Some files were skipped. Use JPG, PNG, or WebP images up to 10 MB each.');
    if (accepted.length > remaining) warnings.push(`You can add up to ${MAX_IMAGES} images. Remove a page to add another.`);
    setNotice(warnings.join(' ') || `${additions.length} ${additions.length === 1 ? 'image added' : 'images added'}.`);
  }

  // Native paste supports multiple files without requiring clipboard permission.
  useEffect(() => {
    function onPaste(event) {
      if (dialogRef.current?.open) return;
      const files = Array.from(event.clipboardData?.files || []);
      if (files.length) { event.preventDefault(); addImages(files); }
    }
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, []);

  async function pasteImages() {
    if (busyRef.current) return;
    if (!navigator.clipboard?.read) {
      setNotice('Click the image area and press Ctrl+V (⌘V on Mac), or choose images from your device.');
      return;
    }
    try {
      const items = await navigator.clipboard.read();
      const files = [];
      for (const item of items) {
        const type = item.types.find(type => IMAGE_TYPES.includes(type));
        if (type) {
          const blob = await item.getType(type);
          files.push(new File([blob], `Pasted flyer ${files.length + 1}.${type.split('/')[1]}`, { type }));
        }
      }
      if (files.length) addImages(files);
      else setNotice('No supported images on your clipboard. Copy a flyer image first, or choose images from your device.');
    } catch {
      setNotice('Clipboard access isn’t available. Press Ctrl+V (⌘V on Mac) to paste, or choose images from your device.');
    }
  }

  function removeImage(id) {
    if (busyRef.current) return;
    setError('');
    const image = imageRef.current.find(image => image.id === id);
    if (image) URL.revokeObjectURL(image.url);
    imageRef.current = imageRef.current.filter(image => image.id !== id);
    setImages(imageRef.current);
    setShowRecipes(false);
    setNotice('Image removed.');
  }

  async function suggestRecipes() {
    if (busyRef.current || !imageRef.current.length) return;
    busyRef.current = true;
    setLoading(true);
    setError('');
    setNotice('');
    setShowRecipes(false);
    setResult(null);
    try {
      const data = await extractAndMatch(imageRef.current.map(image => image.file));
      setResult(data);
      setShowRecipes(true);
    } catch (error) {
      setError(error.message || 'Unable to get recipe suggestions.');
    } finally {
      busyRef.current = false;
      setLoading(false);
    }
  }

  return <div className="min-h-dvh bg-canvas text-ink">
    <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-6 sm:px-10">
      <div className="flex items-center gap-2.5"><span className="brand-mark"><Sprout size={23}/></span><span className="font-serif text-3xl tracking-tight">gather<span className="text-olive">.</span></span></div>
      <span className="text-[10px] uppercase tracking-[.16em] text-muted">From flyer to table</span>
    </header>
    <main className="mx-auto max-w-4xl px-5 pb-16 pt-9 sm:px-10 sm:pt-14">
      <section className="text-center" aria-labelledby="page-title">
        <p className="eyebrow">SMALL SAVINGS. GOOD FOOD.</p>
        <h1 id="page-title" className="mt-5 font-serif text-[40px] leading-[1.12] tracking-[-.035em] sm:text-[56px]">This week’s deals.<br/><span className="text-olive">Your next good meal.</span></h1>
        <p className="mx-auto mt-5 max-w-md text-sm leading-7 text-muted">Add your grocery flyers in one place.<br/>Turn the ingredients on sale into a little dinner inspiration.</p>
      </section>

      <section className="mt-10 rounded-3xl border border-line bg-paper p-4 shadow-[0_8px_40px_#514b3508] sm:p-7" aria-label="Add flyer images" aria-busy={loading}>
        <fieldset disabled={loading} className="min-w-0 disabled:opacity-60">
        <div tabIndex={0} aria-label="Flyer image area. Paste with Control V or Command V, or drop image files here."
          onDragOver={event => { event.preventDefault(); setDragging(true); }}
          onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget)) setDragging(false); }}
          onDrop={event => { event.preventDefault(); setDragging(false); addImages(event.dataTransfer.files); }}
          className={`rounded-2xl border-2 border-dashed px-4 py-10 text-center outline-offset-4 transition focus-visible:outline-olive sm:py-12 ${dragging ? 'border-olive bg-[#e9ecdf]' : 'border-[#d8d7c7] bg-[#f7f6ef]'}`}>
          <span className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-[#e8ecdb] text-olive"><ImagePlus size={27} strokeWidth={1.5}/></span>
          <h2 className="mt-5 font-serif text-2xl">Paste your flyer images here</h2>
          <p className="mt-2 text-xs leading-6 text-muted">One page or a whole week’s worth. Paste, drag & drop, or browse.</p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button onClick={pasteImages} className="flex items-center gap-2 rounded-xl bg-olive px-5 py-3 text-sm text-white transition hover:bg-olive-dark"><ClipboardPaste size={16}/>Paste images</button>
            <button onClick={() => inputRef.current?.click()} className="flex items-center gap-2 rounded-xl border border-line bg-paper px-5 py-3 text-sm transition hover:bg-sidebar"><Upload size={16}/>Choose images</button>
          </div>
          <p className="mt-5 text-[11px] text-muted">Ctrl + V / ⌘ + V · JPG, PNG, WebP · Up to 10 images, 10 MB each</p>
        </div>
        <input ref={inputRef} type="file" multiple accept="image/jpeg,image/png,image/webp" className="hidden" onChange={event => { addImages(event.target.files); event.target.value = ''; }}/>
        <p role="status" className="mt-3 text-xs leading-5 text-muted">{notice}</p>
        {images.length > 0 && <div className="mt-5">
          <div className="mb-4 flex items-center justify-between"><h3 className="text-sm font-medium">Your flyer pages <span className="ml-1 text-muted">({images.length}/{MAX_IMAGES})</span></h3><button onClick={() => inputRef.current?.click()} disabled={images.length >= MAX_IMAGES} className="flex items-center gap-1 text-xs text-olive disabled:cursor-not-allowed disabled:opacity-40"><Plus size={14}/>Add more</button></div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">{images.map((image, index) => <figure key={image.id} className="relative overflow-hidden rounded-xl border border-line bg-canvas">
            <img src={image.url} alt={`Flyer page ${index + 1}: ${image.file.name}`} className="h-36 w-full object-contain p-2"/>
            <button onClick={() => removeImage(image.id)} aria-label={`Remove flyer page ${index + 1}`} className="absolute right-2 top-2 rounded-full border border-line bg-paper p-1.5 text-muted hover:text-ink"><X size={13}/></button>
            <figcaption className="truncate border-t border-line px-3 py-2 text-[11px] text-muted" title={image.file.name}>{index + 1}. {image.file.name}</figcaption>
          </figure>)}</div>
        </div>}
        <div className="mt-6 flex flex-col items-center justify-between gap-4 border-t border-line pt-5 sm:flex-row">
          <p className="max-w-xs text-xs leading-5 text-muted">Find meals using ingredients from your flyers. Processing several pages may take a few minutes.</p>
          <button disabled={!images.length || loading} onClick={suggestRecipes} className="flex w-full shrink-0 items-center justify-center gap-3 rounded-xl bg-olive px-6 py-3.5 text-sm font-medium text-white transition hover:bg-olive-dark disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto">{loading ? 'Finding recipes…' : 'Find recipe suggestions'}{loading ? <LoaderCircle size={16} className="animate-spin"/> : <ArrowRight size={16}/>}</button>
        </div>
        </fieldset>
        {loading && <p role="status" className="mt-4 text-sm text-olive">Reading your flyers and choosing recipes. Please keep this page open.</p>}
        {error && <p role="alert" className="mt-4 break-words rounded-xl border border-[#dec5b8] bg-[#f5e8df] p-4 text-sm text-[#803e2e]">{error}</p>}
      </section>

      {showRecipes && <section ref={resultsRef} className="mt-12 scroll-mt-8" aria-labelledby="recipes-title" aria-live="polite">
        <p className="eyebrow">A LITTLE DINNER INSPIRATION</p><h2 id="recipes-title" className="mt-3 font-serif text-3xl">Something good for your table.</h2>
        <p className="mt-3 text-sm leading-6 text-muted">{result.items.length} flyer items found · {result.matched_recipes.length} recipe suggestions</p>
        {!result.matched_recipes.length && <p className="mt-5 rounded-xl border border-line bg-paper p-5 text-sm text-muted">{result.items.length ? 'No matching recipes found. Try adding another flyer.' : 'No food items were found. Try a clearer flyer image.'}</p>}
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{result.matched_recipes.map((recipe, index) => <article key={recipe.id ?? index} className="overflow-hidden rounded-2xl border border-line bg-paper">
          <div className={`recipe-picture ${['peach', 'sage', 'ochre'][index % 3]}`}><Bowl small color={['peach', 'sage', 'ochre'][index % 3]}/><span className="sample-label">Suggestion {index + 1} · Illustration</span></div>
          <div className="p-5"><h3 className="font-serif text-xl leading-tight">{recipe.title}</h3>{recipe.reason && <p className="mt-3 text-xs leading-6 text-muted">{recipe.reason}</p>}<button onClick={() => setSelected(recipe)} className="mt-5 flex items-center gap-2 text-xs font-medium text-olive">View recipe<ArrowRight size={13}/></button></div>
        </article>)}</div>
      </section>}
      <p className="mt-9 text-center font-serif text-sm italic text-muted">Good for your plate. Gentler on your grocery budget.</p>
    </main>
    <dialog ref={dialogRef} aria-labelledby="recipe-title" onCancel={() => setSelected(null)} onClick={event => { if (event.target === event.currentTarget) setSelected(null); }} className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-3xl border border-line bg-canvas p-7 text-ink shadow-xl backdrop:bg-black/30">
      <button onClick={() => setSelected(null)} className="icon-button float-right" aria-label="Close recipe"><X size={20}/></button>
      {selected && <><p className="eyebrow">YOUR RECIPE SUGGESTION</p><h2 id="recipe-title" className="mt-4 font-serif text-3xl">{selected.title}</h2>{selected.reason && <p className="mt-4 text-sm leading-7 text-muted">{selected.reason}</p>}<h3 className="mt-7 text-sm font-semibold">Ingredients</h3><p className="mt-2 text-sm leading-7 text-muted">{selected.ingredient_text || 'See the original recipe for ingredients.'}</p>{recipeUrl(selected.link) ? <a href={recipeUrl(selected.link)} target="_blank" rel="noopener noreferrer" className="mt-6 inline-flex items-center gap-2 rounded-xl bg-olive px-5 py-3 text-sm text-white">Open full recipe<ArrowRight size={16}/></a> : <p className="mt-5 text-xs text-muted">No recipe link was provided.</p>}</>}
    </dialog>
  </div>;
}
