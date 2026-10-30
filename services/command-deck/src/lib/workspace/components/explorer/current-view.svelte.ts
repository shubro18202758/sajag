/**
 * The saved view in force on this page: the one last applied or saved from
 * the Explorer (its row is `.is-selected`; it reads "edited" once the
 * workspace moves away from it). Page state only — nothing is stored.
 */
class CurrentView {
	id = $state<string | null>(null);

	set(id: string | null): void {
		this.id = id;
	}
}

export const currentView = new CurrentView();
