<script>
	// Onglet « IA pilote » : ce que l'IA locale regarde, ce qu'elle propose,
	// ce qui a été changé, et si le changement a été meilleur ou pire.
	//
	// Règle de lecture de cette page : rien n'est inventé. Les chiffres viennent
	// de la base des trades, les alertes sont calculées par le programme, et une
	// modification appliquée peut toujours être annulée d'un clic.
	import { onDestroy, onMount } from 'svelte';

	let pilote = null;
	let chargement = false;
	let messageAction = '';
	let erreur = '';
	let intervalle = null;

	const NIVEAUX = [
		{ valeur: 0, libelle: 'Éteint', detail: 'l’IA ne fait rien du tout' },
		{ valeur: 1, libelle: 'Bilan seul', detail: 'elle écrit une phrase par heure' },
		{ valeur: 2, libelle: 'Propositions', detail: 'elle propose, tu approuves' },
		{ valeur: 3, libelle: 'Applique seule', detail: 'elle change, avec retour automatique' }
	];

	async function charger() {
		if (chargement) return;
		chargement = true;
		erreur = '';
		try {
			const r = await fetch('/api/ia/pilotage');
			if (!r.ok) throw new Error('réponse ' + r.status);
			pilote = await r.json();
		} catch (e) {
			erreur = 'Le robot n’a pas répondu à la page IA. Il continue de tourner à côté.';
		} finally {
			chargement = false;
		}
	}

	async function action(route, corps, libelle) {
		chargement = true;
		messageAction = libelle + '…';
		try {
			const r = await fetch('/api/ia/pilotage/' + route, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(corps || {})
			});
			const donnees = await r.json();
			if (donnees.ok === false) {
				messageAction = donnees.motif || 'Le robot a refusé.';
			} else {
				messageAction = '';
				pilote = donnees;
			}
		} catch (e) {
			erreur = 'La commande n’est pas arrivée au robot.';
			messageAction = '';
		} finally {
			chargement = false;
		}
	}

	function cageDe(cle) {
		return (pilote?.cage || []).find((c) => c.cle === cle) || null;
	}

	function nombre(valeur, cle) {
		if (valeur === null || valeur === undefined) return '—';
		const regle = cageDe(cle);
		if (regle && regle.fraction) return (valeur * 100).toFixed(0) + ' %';
		if (regle && regle.unite === '%') return valeur.toFixed(2) + ' %';
		if (regle && regle.unite) return valeur.toFixed(2) + ' ' + regle.unite;
		return String(valeur);
	}

	function argent(valeur) {
		if (valeur === null || valeur === undefined) return '—';
		const signe = valeur > 0 ? '+' : '';
		return signe + Number(valeur).toFixed(2);
	}

	function heure(iso) {
		if (!iso) return '—';
		const d = new Date(iso);
		return isNaN(d.getTime()) ? iso : d.toLocaleString('fr-FR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' });
	}

	function etatFrancais(etat) {
		return (
			{ propose: 'en attente', applique: 'appliqué', annule: 'annulé', rejete: 'rejeté', expire: 'expiré' }[etat] || etat
		);
	}

	$: pret = !!(pilote && pilote.actif && pilote.modele);
	$: bilan = pilote?.bilan || null;
	$: propositions = pilote?.propositions || [];
	$: decisions = pilote?.decisions || [];
	$: cage = pilote?.cage || [];

	onMount(() => {
		charger();
		intervalle = setInterval(charger, 30000);
	});

	onDestroy(() => {
		if (intervalle) clearInterval(intervalle);
	});
</script>

<section class="pilote">
	<header>
		<span class="pastille" class:pret={pret} aria-hidden="true"></span>
		<h2>IA pilote</h2>
		<span class="modele" title="modèle déjà en mémoire vidéo">{pilote?.modele || 'aucun modèle chargé'}</span>
	</header>

	<p class="note">
		{pilote?.message || 'Le robot n’a pas encore répondu.'}
		<span class="sep">·</span>
		elle ne peut toucher que six réglages, toujours dans des bornes, et chaque changement est mesuré.
	</p>

	{#if erreur}
		<div class="bandeau erreur">
			{erreur}
			<button class="discret" on:click={charger}>Réessayer</button>
		</div>
	{/if}

	{#if messageAction}
		<p class="message">{messageAction}</p>
	{/if}

	{#if pilote?.attention}
		<div class="bandeau attention">⏳ {pilote.attention}</div>
	{/if}

	<div class="carte">
		<h3>Niveau du pilote</h3>
		<div class="niveaux">
			{#each NIVEAUX as niveau}
				<button
					class="niveau"
					class:actif={pilote && pilote.niveau === niveau.valeur}
					disabled={chargement}
					title={niveau.detail}
					on:click={() => action('niveau', { niveau: niveau.valeur }, 'Niveau ' + niveau.valeur)}
				>
					<strong>{niveau.libelle}</strong>
					<span>{niveau.detail}</span>
				</button>
			{/each}
		</div>
	</div>

	<div class="carte">
		<h3>
			Bilan de la dernière heure
			<button class="discret" disabled={chargement} on:click={() => action('bilan', {}, 'Bilan en cours')}>
				Faire un bilan maintenant
			</button>
		</h3>
		{#if bilan}
			<p class="heure">{heure(bilan.heure)}</p>
			<p class="texte">{bilan.texte}</p>
			{#if bilan.drapeaux?.length}
				<div class="pastilles">
					{#each bilan.drapeaux as drapeau}
						<span class="pastille-alerte">{drapeau}</span>
					{/each}
				</div>
			{/if}
			{#if bilan.chiffres}
				<div class="chiffres">
					<div><span>prises</span><strong>{bilan.chiffres.trades ?? '—'}</strong></div>
					<div><span>gagnées</span><strong>{bilan.chiffres.gagnes ?? '—'}</strong></div>
					<div><span>en dollars</span><strong>{argent(bilan.chiffres.dollars)}</strong></div>
					<div><span>en points</span><strong>{argent(bilan.chiffres.points)}</strong></div>
				</div>
			{/if}
		{:else}
			<p class="vide">Aucun bilan pour l’instant — le robot en écrit un toutes les heures.</p>
		{/if}
	</div>

	<div class="carte">
		<h3>Ce que l’IA propose</h3>
		{#if propositions.length}
			{#each propositions as proposition}
				<div class="ligne proposition">
					<div class="tete">
						<strong>{proposition.nom || proposition.cle}</strong>
						<span class="valeur">
							{nombre(proposition.avant, proposition.cle)} → <b>{nombre(proposition.apres, proposition.cle)}</b>
						</span>
					</div>
					{#if proposition.motif}<p class="motif">{proposition.motif}</p>{/if}
					<p class="bornes">
						autorisé de {nombre(cageDe(proposition.cle)?.min, proposition.cle)} à {nombre(cageDe(proposition.cle)?.max, proposition.cle)}
					</p>
					<div class="actions">
						<button
							class="principal"
							disabled={chargement}
							on:click={() => action('approuver', { id: proposition.id }, 'Application')}
						>
							Approuver
						</button>
						<button class="secondaire" disabled={chargement} on:click={() => action('rejeter', { id: proposition.id }, 'Rejet')}>
							Rejeter
						</button>
					</div>
				</div>
			{/each}
		{:else}
			<p class="vide">Aucune proposition en attente.</p>
		{/if}
	</div>

	<div class="carte">
		<h3>Décisions récentes</h3>
		{#if decisions.length}
			<table>
				<thead>
					<tr><th>réglage</th><th>avant → après</th><th>état</th><th>mesure</th><th></th></tr>
				</thead>
				<tbody>
					{#each decisions as decision}
						<tr>
							<td>{decision.nom || decision.cle}</td>
							<td class="monospace">{nombre(decision.avant, decision.cle)} → {nombre(decision.apres, decision.cle)}</td>
							<td>
								<span class="etat etat-{decision.etat}">{etatFrancais(decision.etat)}</span>
							</td>
							<td>
								{#if decision.mesure_avant != null || decision.mesure_apres != null}
									{argent(decision.mesure_avant)} → {argent(decision.mesure_apres)}
									{#if decision.verdict}<span class="verdict">{decision.verdict}</span>{/if}
								{:else}
									<span class="vide-en-ligne">à mesurer</span>
								{/if}
							</td>
							<td class="droite">
								{#if decision.etat === 'propose'}
									<button class="principal petit" disabled={chargement} on:click={() => action('approuver', { id: decision.id }, 'Application')}>
										Approuver
									</button>
								{:else if decision.etat === 'applique'}
									<button class="secondaire petit" disabled={chargement} on:click={() => action('annuler', { id: decision.id }, 'Retour')}>
										Annuler
									</button>
								{:else}
									<span class="vide-en-ligne">{heure(decision.applique_le || decision.cree_le)}</span>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{:else}
			<p class="vide">Rien de changé depuis le démarrage.</p>
		{/if}
	</div>

	<div class="carte">
		<h3>Ce qu’elle a le droit de toucher</h3>
		<table>
			<thead>
				<tr><th>réglage</th><th>valeur actuelle</th><th>autorisé de</th><th>à</th></tr>
			</thead>
			<tbody>
				{#each cage as regle}
					<tr>
						<td>{regle.nom}</td>
						<td class="monospace">{nombre(regle.valeur, regle.cle)}</td>
						<td class="monospace">{nombre(regle.min, regle.cle)}</td>
						<td class="monospace">{nombre(regle.max, regle.cle)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="note petite">
			La taille des prises, les plafonds de perte, les frais et le passage en réel ne sont pas dans cette liste :
			l’IA ne peut pas les modifier, et aucun argument ne le permet.
		</p>
	</div>
</section>

<style>
	.pilote {
		background: var(--glass-bg);
		backdrop-filter: var(--glass-blur);
		border: 1px solid var(--border-soft);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-md);
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 14px;
		font-family: var(--font-ui);
		color: var(--text-primary);
	}

	header {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
	}

	h2 {
		margin: 0;
		font-size: 16px;
		font-weight: 700;
	}

	h3 {
		margin: 0 0 10px;
		font-size: 13.5px;
		font-weight: 700;
		color: var(--text-primary);
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		flex-wrap: wrap;
	}

	.modele {
		font-size: 11.5px;
		color: var(--text-secondary);
		font-family: 'JetBrains Mono Variable', monospace;
	}

	.note {
		margin: 0;
		font-size: 12.5px;
		color: var(--text-secondary);
		line-height: 1.5;
	}

	.note.petite {
		margin-top: 8px;
		font-size: 11.5px;
	}

	.sep {
		margin: 0 6px;
		opacity: 0.5;
	}

	.pastille {
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: var(--text-secondary);
		opacity: 0.55;
	}

	.pastille.pret {
		background: var(--accent-green);
		opacity: 1;
		box-shadow: 0 0 8px rgba(var(--accent-green-rgb), 0.55);
	}

	.carte {
		border: 1px solid var(--border-soft);
		border-radius: var(--radius-md);
		padding: 12px;
		background: rgba(var(--accent-green-rgb), 0.02);
	}

	.bandeau {
		border-radius: var(--radius-md);
		padding: 9px 12px;
		font-size: 12.5px;
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
	}

	.bandeau.erreur {
		background: rgba(var(--accent-red-rgb), 0.1);
		border: 1px solid rgba(var(--accent-red-rgb), 0.35);
		color: var(--accent-red);
	}

	.bandeau.attention {
		background: rgba(var(--accent-green-rgb), 0.08);
		border: 1px solid rgba(var(--accent-green-rgb), 0.28);
	}

	.message {
		margin: 0;
		font-size: 12.5px;
		color: var(--text-secondary);
	}

	.niveaux {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 8px;
	}

	.niveau {
		display: flex;
		flex-direction: column;
		gap: 3px;
		text-align: left;
		padding: 9px 11px;
		border-radius: var(--radius-md);
		border: 1px solid var(--border-soft);
		background: transparent;
		color: var(--text-secondary);
		cursor: pointer;
		font-family: var(--font-ui);
		transition: background 0.2s, color 0.2s, border-color 0.2s;
	}

	.niveau strong {
		font-size: 12.5px;
		color: var(--text-primary);
	}

	.niveau span {
		font-size: 11px;
		line-height: 1.35;
	}

	.niveau.actif {
		border-color: rgba(var(--accent-green-rgb), 0.5);
		background: rgba(var(--accent-green-rgb), 0.12);
	}

	.heure {
		margin: 0 0 6px;
		font-size: 11.5px;
		color: var(--text-secondary);
	}

	.texte {
		margin: 0;
		font-size: 13px;
		line-height: 1.55;
		white-space: pre-wrap;
	}

	.pastilles {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-top: 9px;
	}

	.pastille-alerte {
		font-size: 11.5px;
		padding: 3px 8px;
		border-radius: 999px;
		background: rgba(var(--accent-red-rgb), 0.12);
		border: 1px solid rgba(var(--accent-red-rgb), 0.3);
	}

	.chiffres {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
		gap: 8px;
		margin-top: 10px;
	}

	.chiffres div {
		border: 1px solid var(--border-soft);
		border-radius: var(--radius-md);
		padding: 7px 9px;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.chiffres span {
		font-size: 11px;
		color: var(--text-secondary);
	}

	.chiffres strong {
		font-size: 14px;
		font-family: 'JetBrains Mono Variable', monospace;
	}

	.ligne.proposition {
		border: 1px solid var(--border-soft);
		border-radius: var(--radius-md);
		padding: 10px 12px;
		margin-bottom: 8px;
	}

	.tete {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 10px;
		flex-wrap: wrap;
		font-size: 13px;
	}

	.valeur {
		font-family: 'JetBrains Mono Variable', monospace;
		font-size: 12.5px;
		color: var(--text-secondary);
	}

	.motif {
		margin: 6px 0 4px;
		font-size: 12.5px;
		line-height: 1.5;
	}

	.bornes {
		margin: 0 0 8px;
		font-size: 11.5px;
		color: var(--text-secondary);
	}

	.actions {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}

	button {
		font-family: var(--font-ui);
		cursor: pointer;
		border-radius: var(--radius-md);
		padding: 7px 12px;
		font-size: 12.5px;
		border: 1px solid var(--border-soft);
		background: transparent;
		color: var(--text-primary);
		transition: background 0.2s, border-color 0.2s, opacity 0.2s;
	}

	button.petit {
		padding: 5px 10px;
		font-size: 11.5px;
	}

	button.principal {
		background: rgba(var(--accent-green-rgb), 0.16);
		border-color: rgba(var(--accent-green-rgb), 0.45);
		color: var(--accent-green);
		font-weight: 600;
	}

	button.secondaire:hover {
		border-color: rgba(var(--accent-red-rgb), 0.45);
		color: var(--accent-red);
	}

	button.discret {
		font-size: 11.5px;
		padding: 5px 9px;
		color: var(--text-secondary);
	}

	button:disabled {
		opacity: 0.5;
		cursor: default;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 12.5px;
	}

	th {
		text-align: left;
		font-size: 11px;
		font-weight: 600;
		color: var(--text-secondary);
		padding: 4px 8px 8px;
		border-bottom: 1px solid var(--border-soft);
	}

	td {
		padding: 7px 8px;
		border-bottom: 1px solid var(--border-soft);
		vertical-align: middle;
	}

	tr:last-child td {
		border-bottom: none;
	}

	.monospace {
		font-family: 'JetBrains Mono Variable', monospace;
		font-size: 12px;
	}

	.droite {
		text-align: right;
	}

	.etat {
		font-size: 11.5px;
		padding: 2px 8px;
		border-radius: 999px;
		border: 1px solid var(--border-soft);
		white-space: nowrap;
	}

	.etat-propose {
		color: var(--text-secondary);
	}

	.etat-applique {
		color: var(--accent-green);
		border-color: rgba(var(--accent-green-rgb), 0.4);
	}

	.etat-annule,
	.etat-rejete,
	.etat-expire {
		color: var(--accent-red);
		border-color: rgba(var(--accent-red-rgb), 0.35);
	}

	.verdict {
		font-size: 11px;
		margin-left: 6px;
		color: var(--text-secondary);
	}

	.vide,
	.vide-en-ligne {
		color: var(--text-secondary);
		font-size: 12px;
	}

	.vide {
		margin: 0;
	}

	@media (max-width: 700px) {
		th:nth-child(4),
		td:nth-child(4) {
			display: none;
		}
	}
</style>
