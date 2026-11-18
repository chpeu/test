<script>
	// Carte « conseiller IA locale » : affiche l'état du service, et recueille
	// l'avis du modèle DÉJÀ chargé dans llama-swap. Aucun bouton ne passe
	// d'ordre : le robot décide seul, l'IA commente le journal.
	import { onMount } from 'svelte';

	let etat = null;
	let question = '';
	let reponse = '';
	let enCours = false;
	let message = '';

	async function chargerEtat() {
		try {
			const r = await fetch('/api/ia/etat');
			etat = await r.json();
		} catch (e) {
			etat = { service_joignable: false, message: "Le serveur d'IA ne répond pas." };
		}
	}

	async function demander(corps, libelle) {
		enCours = true;
		message = libelle + '…';
		reponse = '';
		try {
			const r = await fetch('/api/ia/' + corps.route, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(corps.corps)
			});
			const donnees = await r.json();
			if (donnees.ok) {
				reponse = donnees.texte;
				message = 'Réponse de ' + (donnees.modele || 'l’IA') + '.';
			} else {
				message = donnees.motif || 'L’IA n’a pas répondu.';
			}
		} catch (e) {
			message = 'Le serveur d’IA n’a pas répondu (le robot continue de tourner).';
		} finally {
			enCours = false;
		}
	}

	// valeur réactive simple : Svelte ne suit pas les dépendances cachées dans
	// une fonction appelée dans class:..., d'où la pastille restée grise.
	$:	ia_prete = !!(etat && etat.service_joignable && etat.modele);

	onMount(chargerEtat);
</script>

<section class="ia">
	<header>
		<span class="pastille" class:pret={ia_prete} aria-hidden="true"></span>
		<h2>Conseiller IA locale</h2>
		<span class="modele" title="modèle déjà en mémoire vidéo">{etat?.modele || 'aucun modèle chargé'}</span>
	</header>

	<p class="note">
		{etat?.message || 'État inconnu.'}
		<span class="sep">·</span>
		lecture seule : il commente le journal, il ne passe jamais d’ordre.
	</p>

	<textarea
		bind:value={question}
		rows="2"
		placeholder="Ex. : qu’est-ce qui revient le plus dans mes sorties ?"
		disabled={enCours}
	/>

	<div class="actions">
		<button
			class="principal"
			disabled={enCours || !question.trim()}
			on:click={() => demander({ route: 'avis', corps: { question } }, 'Question en cours')}
		>
			Demander un avis
		</button>
		<button disabled={enCours} on:click={() => demander({ route: 'bilan', corps: { limite: 30 } }, 'Lecture du journal')}>
			Bilan du journal
		</button>
		<button class="discret" disabled={enCours} on:click={chargerEtat}>Vérifier l’état</button>
	</div>

	{#if message}
		<p class="message">{message}</p>
	{/if}

	{#if reponse}
		<div class="reponse">{reponse}</div>
	{/if}
</section>

<style>
	.ia {
		background: var(--bg-secondary);
		border: 1px solid var(--border-soft);
		border-radius: 14px;
		padding: 14px 16px;
		margin-bottom: 18px;
		display: grid;
		gap: 10px;
	}

	header {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	h2 {
		margin: 0;
		font-size: 15px;
		font-weight: 600;
		color: var(--text-primary);
	}

	.pastille {
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: var(--text-faint);
		flex: none;
	}

	.pastille.pret {
		background: var(--accent-green);
		box-shadow: 0 0 0 3px rgba(var(--accent-green-rgb), 0.18);
	}

	.modele {
		margin-left: auto;
		font-family: var(--font-mono);
		font-size: 11px;
		color: var(--text-faint);
		max-width: 46%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.note {
		margin: 0;
		font-size: 12.5px;
		color: var(--text-secondary);
		line-height: 1.5;
	}

	.sep {
		margin: 0 6px;
		color: var(--text-faint);
	}

	textarea {
		width: 100%;
		resize: vertical;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 10px;
		color: var(--text-primary);
		font: inherit;
		font-size: 13px;
		padding: 9px 11px;
	}

	textarea:focus {
		outline: none;
		border-color: var(--accent-blue);
	}

	.actions {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}

	button {
		border: 1px solid var(--border);
		background: var(--bg-tertiary);
		color: var(--text-primary);
		border-radius: 9px;
		padding: 7px 12px;
		font-size: 12.5px;
		cursor: pointer;
	}

	button:hover:not(:disabled) {
		border-color: var(--border-strong);
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	button.principal {
		background: rgba(var(--accent-blue-rgb), 0.16);
		border-color: rgba(var(--accent-blue-rgb), 0.45);
	}

	button.discret {
		background: transparent;
		color: var(--text-secondary);
	}

	.message {
		margin: 0;
		font-size: 12px;
		color: var(--text-secondary);
	}

	.reponse {
		white-space: pre-wrap;
		background: var(--bg-primary);
		border: 1px solid var(--border-soft);
		border-left: 2px solid var(--accent-green);
		border-radius: 10px;
		padding: 12px 14px;
		font-size: 13px;
		line-height: 1.6;
		color: var(--text-primary);
	}
</style>
