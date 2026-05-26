
from datetime import date
from rich.console import Console
from rich.table import Table
from rich.box import ROUNDED
from typing import Annotated, Optional

import humanize
import plantera.db as db
import plantera.service as service
import subprocess
import sys
import typer

console = Console()
app = typer.Typer(add_completion=False)

__version__ = "0.1.6"

BANNER = """[green]
  __
 /  \\    ██████╗ ██╗      █████╗ ███╗   ██╗████████╗███████╗██████╗  █████╗
/    \\   ██╔══██╗██║     ██╔══██╗████╗  ██║╚══██╔══╝██╔════╝██╔══██╗██╔══██╗
\\ ~~ /   ██████╔╝██║     ███████║██╔██╗ ██║   ██║   █████╗  ██████╔╝███████║
 \\  /    ██╔═══╝ ██║     ██╔══██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗██╔══██║
  \\/     ██║     ███████╗██║  ██║██║ ╚████║   ██║   ███████╗██║  ██║██║  ██║
  ||     ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝
  ||
[/green]"""

ALLOWED_SETTINGS = ["auto_interval", "diagnose_api_key"]

def version_callback(value: bool) -> None:
  """
  Callback for the --version flag. Prints the version and exits.

  Parameters
  ----------
  value : bool
      True if --version was passed.
  """
  if value:
    typer.echo(f"Plantera v{__version__}")
    raise typer.Exit()


@app.callback(invoke_without_command=True)
def startup(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", callback=version_callback, is_eager=True, help="Show version and exit.")
) -> None:
  """Initialize the database on startup."""

  # Show banner on first run
  first_run = not db.DB_PATH.exists()

  # Initialize the database
  result = db.db_init()
  if result not in [True, None]:
    typer.echo(f"Error initializing database: {str(result)}")

  if first_run:
    Console().print(BANNER, highlight=False)

  if ctx.invoked_subcommand is None:
    Console().print("[dark_orange]Usage:[/dark_orange] [green]plantera[/green] <command>")
    Console().print("Try '[green]plantera[/green] [cornflower_blue]--help[/cornflower_blue]' for more information.")
    raise typer.Exit()


@app.command()
def add(
    nickname: Annotated[str, typer.Argument(help="Name/nickname of the plant")],
    genus: Annotated[str, typer.Argument(help="Type of the plant (must exist in the plant library)")],
    last_watered: Annotated[str, typer.Argument(help="Last watered date (YYYY-MM-DD)")] = str(date.today()),
    interval: Annotated[int, typer.Argument(help="Watering interval (in days)")] = 7,
    environment: Annotated[str, typer.Argument(help="Description of the location and physical environment of the plant")] = ''
) -> None:
  """
  CLI command to add a plant to the database.

  Parameters
  ----------
  nickname : str
      The user's name for the plant (e.g. "Bob")
  genus : str
      The genus of the plant species (must exist in plant_species table)
  last_watered : str
      Date the plant was last watered in YYYY-MM-DD format
  interval : int
      Watering interval in days
  """

  # Add plant to the database
  result = service.add_plant(nickname, genus, last_watered, interval, environment)

  # Check the result and output the appropriate message
  if result is True:
    typer.echo(f"Plant '{nickname}' added successfully!")
  else:
    typer.echo(str(result))


@app.command()
def add_species(
    genus: Annotated[str, typer.Argument(help="Genus of the plant, ie. 'Crassula' or 'Rosa")],
    common_name: Annotated[str, typer.Argument(help="Common name of the plant, ie. 'Jade' or 'Rose")],
    care_info: Annotated[str, typer.Argument(help="Care information for the plant")] = "No care information provided."
) -> None:
  """
  CLI command to add a plant species to the database.

  Parameters
  ----------
  genus : str
      The scientific genus name (e.g. "Crassula")
  common_name : str
      The common name of the plant (e.g. "Jade Plant")
  care_info : str
      Care instructions for the species
  """

  # Add plant species to the database
  result = service.add_plant_species(genus, common_name, care_info)

  # Check the result and output the appropriate message
  if result is True:
    typer.echo(f"Species '{genus} - {common_name}' added successfully!")
  else:
    typer.echo(str(result))


@app.command()
def show(
    name: Annotated[Optional[str], typer.Option(help="Search plants by nickname")] = None,
    species: Annotated[bool, typer.Option(help="Show Species (True / False)")] = False,
    due: Annotated[bool, typer.Option(help="Show only plants due for watering (True / False)")] = False,
) -> None:
  """
  CLI command to show plants in the database.

  Parameters
  ----------
  name : str
      If provided, show a single plant matching the nickname
  species : bool
      If True, show plant species instead of my plants
  due : bool
      If True, show only plants due for watering
  """

  # Check if both species and due are True and output an error message
  if species and due:
    typer.echo("Error: Cannot use --species and --due together.")
    return
  # Check if name and species or due are True and output an error message
  if name and (species or due):
    typer.echo("Error: Cannot use --name with --species or --due.")
    return

  # Show plants based on the specified criteria
  result = service.show_plants(name, species, due)

  if isinstance(result, list):
    if len(result) == 0 and not due:
      typer.echo("No plants in your collection yet. Try 'plantera add --help'.")
    elif len(result) == 0 and name:
      typer.echo(f"No plants found with nickname '{name}'.")
    elif len(result) == 0 and due:
      with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM my_plants")
        plants = cursor.fetchall()
        if len(plants) == 0:
          typer.echo("No plants in your collection yet. Try 'plantera add --help'.")
        else:
          typer.echo("All plants are watered and up to date.")

    else:
      # Results aren't empty format table for output
      if not species:
        # My Plants table can be filtered by due for watering
        table = Table(title="\nPlantera", header_style="bold green", border_style="green", box=ROUNDED, row_styles=["", "bold"])

        table.add_column("Nickname")
        table.add_column("Genus")
        table.add_column("Common Name")
        table.add_column("Last Watered")
        table.add_column("Next Watering")
        table.add_column("Interval")
        table.add_column("Care Info")

        for plant in result:
          next_watering_date = date.fromisoformat(plant['next_watering'])
          if plant['next_watering'] < str(date.today()):
            next_watering = f"[red]{humanize.naturalday(next_watering_date)}[/red]"
          else:
            next_watering = humanize.naturalday(next_watering_date)

          table.add_row(
            plant['nickname'],
            plant['genus'],
            plant['common_name'],
            humanize.naturalday(date.fromisoformat(plant['last_watered'])),
            next_watering,
            f"{str(plant['interval'])} {'day' if plant['interval'] == 1 else 'days'}",
            plant['care_info']
          )

        Console().print(table)
      else:
        # Plant Species table
        table = Table(title="\nPlant Species", header_style="bold green", border_style="green", box=ROUNDED, row_styles=["", "bold"])

        table.add_column("ID")
        table.add_column("Genus")
        table.add_column("Common Name")
        table.add_column("Care Info")

        for row in result:
          table.add_row(str(row['id']), row['genus'], row['common_name'], row['care_info'])

        Console().print(table)

  else:
    typer.echo(result)


@app.command()
def watered(nickname: Annotated[str, typer.Argument(help="Mark plant as watered (Plant nickname)")]) -> None:
  """
  CLI command to mark a plant as watered and recalculate next watering date.

  Parameters
  ----------
  nickname : str
      The plant's nickname
  """

  # Mark plant as watered
  success, result = service.watered(nickname)
  # Check the result and output the appropriate message
  if success:
    typer.echo(f"Plant '{nickname}' marked as watered, next watering is {humanize.naturalday(result)}.")
  else:
    typer.echo(str(result))


@app.command()
def update(
    my_plant: Annotated[str, typer.Argument(help="Nickname of the plant to update")],
    nickname: Annotated[Optional[str], typer.Option(help="New nickname of the plant")] = None,
    genus: Annotated[Optional[str], typer.Option(help="genus of the plant (must exist in the database)")] = None,
    last_watered: Annotated[Optional[str], typer.Option(help="Last watered date (YYYY-MM-DD)")] = None,
    next_watering: Annotated[Optional[str], typer.Option(help="Next watering date (YYYY-MM-DD)")] = None,
    interval: Annotated[Optional[int], typer.Option(help="Watering interval (in days)")] = None,
    environment: Annotated[Optional[str], typer.Option(help="Description of the location and physical environment of the plant")] = None
) -> None:
  """
  CLI command to update a plant in the database.

  Parameters
  ----------
  my_plant : str
      Nickname of the plant to update
  nickname : str, optional
      New nickname for the plant
  genus : str, optional
      New genus (must exist in plant_species table)
  last_watered : str, optional
      New last watered date in YYYY-MM-DD format
  next_watering : str, optional
      Override next watering date in YYYY-MM-DD format
  interval : int, optional
      New watering interval in days
  """

  # Update the plant in the database
  result = service.update_plant(my_plant, nickname, genus, last_watered, next_watering, interval, environment)

  # Check the result and output the appropriate message
  if result is True:
    typer.echo(f"Plant '{my_plant}' updated successfully!")

  elif isinstance(result, str):
    typer.echo(result)

  else:
    typer.echo(str(result))


@app.command()
def update_species(
    genus_to_update: Annotated[str, typer.Argument(help="Genus of the plant to update")],
    genus: Annotated[Optional[str], typer.Option(help="New genus of the plant")] = None,
    common_name: Annotated[Optional[str], typer.Option(help="New common name of the plant")] = None,
    care_info: Annotated[Optional[str], typer.Option(help="Updated care information for the plant")] = None
) -> None:
  """
  CLI command to update a plant species in the database.

  Parameters
  ----------
  genus_to_update : str
      Genus of the species to update
  genus : str, optional
      New genus name
  common_name : str, optional
      New common name
  care_info : str, optional
      Updated care instructions
  """

  # Update the plant species in the database
  result = service.update_species(genus_to_update, genus, common_name, care_info)

  # Check the result and output the appropriate message
  if result is True:
    typer.echo(f"Species '{genus_to_update}' updated successfully!")
  elif isinstance(result, str):
    typer.echo(result)
  else:
    typer.echo(str(result))


@app.command()
def delete(nickname: Annotated[str, typer.Argument(help="Nickname of the plant to delete")]) -> None:
  """
  CLI command to delete a plant from the database.

  Parameters
  ----------
  nickname : str
      Nickname of the plant to delete
  """

  # Confirm deletion with the user
  if not typer.confirm(f"Are you sure you want to delete plant '{nickname}'?"):
    typer.echo("Deletion cancelled.")
    return

  # Delete the plant from the database
  result = service.delete_plant(nickname)

  # Check the result and output the appropriate message
  if result is True:
    typer.echo(f"Plant '{nickname}' deleted successfully!")
  else:
    typer.echo(str(result))


@app.command()
def delete_species(genus: Annotated[str, typer.Argument(help="Genus of the plant to delete")]) -> None:
  """
  CLI command to delete a plant species from the database.

  Parameters
  ----------
  genus : str
      Genus of the species to delete
  """

  # Confirm deletion with the user
  if not typer.confirm(f"Are you sure you want to delete species '{genus}'?"):
    typer.echo("Deletion cancelled.")
    return

  # Delete the plant species from the database
  result = service.delete_species(genus)

  # Check the result and output the appropriate message
  if result is True:
    typer.echo(f"Species '{genus}' deleted successfully!")
  else:
    typer.echo(str(result))

@app.command()
def remind() -> None:
  """
  Send a system notification for plants due for watering.
  """
  # Get plants due for watering
  plants = service.show_plants(None, False, True)
  if len(plants) > 0:
    reminders = []
    # Build reminder message list from due plants
    for plant in plants:
      next_watering = date.fromisoformat(plant['next_watering'])
      reminders.append(f"Water {plant['nickname']} - {plant['common_name']} (Due: {humanize.naturalday(next_watering)})")
    title = "Water Reminder"
    message = '\n'.join(reminders)
    typer.echo(message)

    if sys.platform == "linux":
      # If on Linux, use notify-send to send the notification. Plyer doesn't respect the timeout parameter.
      subprocess.call(["notify-send", "-t", "10000", "-a", "Plantera", title, message])
    else:
      # If on Windows or macOS, use the plyer notification module.
      from plyer import notification
      notification.notify(title=title, message=message, timeout=10)
  else:
    typer.echo("No plants are due for watering.")

@app.command()
def config(setting: Annotated[Optional[str], typer.Argument(help="The setting to enable or update (auto_interval, diagnose_api_key [CLAUDE])")] = None,
           value: Annotated[Optional[str], typer.Option(help="Set the value of the setting")] = None,
           delete: Annotated[bool, typer.Option(help="Delete the setting")] = False
           ) -> None:
  """
  View or update Plantera settings.

  Run without arguments to display all current settings. Provide a setting name
  to update or delete it.

  Parameters
  ----------
  setting : str, optional
      The setting key to update or delete. Allowed values: auto_interval, diagnose_api_key.
  value : str, optional
      The value to set for the given setting.
  delete : bool
      If True, delete the setting row rather than updating it.
  """

  # Validate inputs.
  # value and delete cannot be used together.
  if value and delete:
    typer.echo("Error: Cannot use --value and --delete together.")
    return

  if setting is not None:
    setting = setting.replace('-', '_')

  # If config is run without arguments, return setting values and print a table.
  if setting is None:
    result = service.get_settings()

    if result is not None:
      if isinstance(result, list):
        if len(result) == 0:
          typer.echo("There are no settings configured.")
        else:
          # Results aren't empty format table for output
          table = Table(title="\nSettings", header_style="bold green", border_style="green", box=ROUNDED,
                        row_styles=["", "bold"])

          table.add_column("Setting Name")
          table.add_column("Value")


          for setting in result:
            table.add_row(
              setting['key'],
              setting['value']
            )

          Console().print(table)
      else:
        typer.echo(result)

      return


  # Setting value must exist and be in the ALLOWED_SETTINGS list.
  if setting not in ALLOWED_SETTINGS:
    typer.echo(f"Error: Invalid setting. Allowed settings are: {', '.join(ALLOWED_SETTINGS)}")
    return

  # diagnose_api_key requires a value.
  if setting == "diagnose_api_key" and value is None:
    typer.echo("Error: diagnose_api_key requires a value.")
    return

  # auto_interval - set default value if not set.
  if setting == "auto_interval" and value is None:
    value = '0.4'

  result = service.config_setting(setting, value, delete)

  if result is True:
    typer.echo(f"Setting '{setting}' updated successfully!")
  else:
    typer.echo(str(result))

@app.command()
def diagnose(
    nickname: Annotated[str, typer.Argument(help="The nickname of the plant you wish to diagnose")],
    condition: Annotated[Optional[str], typer.Argument(help="Text description of plant's condition")] = None,
    picture: Annotated[Optional[str], typer.Option(help="Path to picture of plant")] = None,
):


  if condition is None and picture is None:
    typer.echo("Error: You must provide either a condition or a picture to diagnose the plant.")
    return

  result = service.diagnose(nickname, condition, picture)

  console.print(f"\n[bold green]Response from Claude:[/bold green]\n")
  for chunk in result:
    print (chunk, end="", flush=True)
  print()

@app.command()
def update_care_info(
    genus: Annotated[str, typer.Argument(help="Genus of the plant to update")],
):

    result = service.update_care_info(genus)
    console.print(f"\n[bold green]Response from Claude:[/bold green]")
    typer.echo(result)



if __name__ == "__main__":
  app()
